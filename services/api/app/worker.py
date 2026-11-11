"""Long-running ingestion worker (ADR-003): APScheduler driving the ingestion jobs."""

from __future__ import annotations

import asyncio
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.seed import seed_airports
from app.db.session import session_scope
from app.ingestion.http import build_client
from app.ingestion.jobs import (
    run_faa_job,
    run_maintenance,
    run_metar_job,
    run_risk_job,
    run_taf_job,
)

log = get_logger(__name__)


async def run_worker() -> None:
    s = get_settings()
    with session_scope() as ses:
        seed_airports(ses)

    client = build_client()
    scheduler = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120},
    )
    scheduler.add_job(
        run_faa_job,
        IntervalTrigger(seconds=s.faa_poll_seconds, jitter=15),
        kwargs={"client": client},
        id="faa",
    )
    scheduler.add_job(
        run_metar_job,
        IntervalTrigger(seconds=s.metar_poll_seconds, jitter=30),
        kwargs={"client": client},
        id="metar",
    )
    scheduler.add_job(
        run_taf_job,
        IntervalTrigger(seconds=s.taf_poll_seconds, jitter=60),
        kwargs={"client": client},
        id="taf",
    )
    scheduler.add_job(
        run_risk_job,
        IntervalTrigger(seconds=s.risk_poll_seconds, jitter=20),
        id="risk",
    )
    scheduler.add_job(run_maintenance, CronTrigger(hour=3, minute=17), id="purge_bronze")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    scheduler.start()
    log.info("worker_started", jobs=[j.id for j in scheduler.get_jobs()])
    # Prime all sources immediately rather than waiting a full interval.
    await asyncio.gather(
        run_faa_job(client=client, trigger="startup"),
        run_metar_job(client=client, trigger="startup"),
        run_taf_job(client=client, trigger="startup"),
    )
    await run_risk_job(trigger="startup")
    await stop.wait()
    log.info("worker_stopping")
    scheduler.shutdown(wait=False)
    await client.aclose()
