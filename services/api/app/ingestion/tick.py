"""Due-jobs "tick" for hosts without an always-on worker (serverless).

An external scheduler (GitHub Actions cron) calls ``POST /api/v1/ingest/tick``. Only jobs
whose interval has elapsed since their last run are executed, under a PostgreSQL advisory
lock, so calling the endpoint more often can never increase upstream polling or run jobs
concurrently. That is why the endpoint needs no secret.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.session import get_engine, session_scope
from app.ingestion.jobs import JOBS, run_maintenance
from app.models import IngestionRun

LOCK_KEY = 0x0AE20F1C  # arbitrary, stable
ORDER = ("faa", "metar", "taf", "risk", "purge")
SLACK = 0.9  # run when >= 90% of the interval has elapsed (absorbs cron jitter)


def intervals() -> dict[str, int]:
    s = get_settings()
    return {
        "faa": s.faa_poll_seconds,
        "metar": s.metar_poll_seconds,
        "taf": s.taf_poll_seconds,
        "risk": s.risk_poll_seconds,
        "purge": 86_400,
    }


def due_jobs(now: dt.datetime) -> list[str]:
    with session_scope() as s:
        last = dict(
            s.execute(
                select(IngestionRun.job, func.max(IngestionRun.started_at)).group_by(
                    IngestionRun.job
                )
            ).all()
        )
    iv = intervals()
    return [
        j for j in ORDER if last.get(j) is None or (now - last[j]).total_seconds() >= iv[j] * SLACK
    ]


async def tick() -> dict[str, Any]:
    now = dt.datetime.now(dt.UTC)
    conn = get_engine().connect()
    try:
        if not conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}):
            return {"ran": [], "skipped": "another tick is running"}
        try:
            results = []
            for job in due_jobs(now):
                if job == "purge":
                    purged = await asyncio.to_thread(run_maintenance, "tick")
                    results.append({"job": job, "status": "success", "purged": purged})
                    continue
                summary = await JOBS[job](trigger="tick")
                results.append(
                    {
                        "job": job,
                        "run_id": summary.run_id,
                        "status": summary.status,
                        "error": summary.error,
                    }
                )
            return {"ran": results}
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
    finally:
        conn.close()
