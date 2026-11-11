"""Health, system status, data freshness and the authenticated ingestion trigger."""

from __future__ import annotations

import hmac
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app import repositories as repo
from app.api.deps import DbSession, meta, now_utc
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.ingestion.jobs import JOBS
from app.ingestion.tick import tick
from app.schemas import (
    Envelope,
    HealthOut,
    IngestionRunOut,
    QualityCheckOut,
    SourceFreshness,
    SystemStatusOut,
)
from app.services import assemblers as asm

router = APIRouter(tags=["system"])

_HEALTH_ORDER = ["healthy", "delayed", "stale", "unavailable"]


def _db_ok() -> bool:
    try:
        with get_sessionmaker()() as s:
            s.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@router.get("/health", response_model=HealthOut, summary="Liveness + database connectivity")
def health(response: Response) -> HealthOut:
    ok = _db_ok()
    if not ok:
        response.status_code = 503
    s = get_settings()
    return HealthOut(
        status="ok" if ok else "degraded",
        version=__version__,
        environment=s.app_env,
        database="ok" if ok else "unavailable",
        time=now_utc(),
    )


@router.get("/data-freshness", response_model=Envelope[list[SourceFreshness]])
def data_freshness(db: DbSession, response: Response) -> Envelope[list[SourceFreshness]]:
    response.headers["Cache-Control"] = "public, max-age=15"
    return Envelope(data=list(asm.all_freshness(db, now_utc()).values()), meta=meta())


@router.get("/status", response_model=Envelope[SystemStatusOut])
def system_status(db: DbSession, response: Response) -> Envelope[SystemStatusOut]:
    response.headers["Cache-Control"] = "public, max-age=15"
    now = now_utc()
    sources = asm.all_freshness(db, now)
    live = [sources[k].health for k in ("faa_nas_status", "awc_metar", "awc_taf")]
    overall = max(live, key=_HEALTH_ORDER.index)
    return Envelope(
        data=SystemStatusOut(
            overall=overall,
            sources=list(sources.values()),
            recent_runs=[IngestionRunOut.model_validate(r) for r in repo.recent_runs(db, 15)],
            latest_quality=[QualityCheckOut.model_validate(q) for q in repo.latest_quality(db)],
        ),
        meta=meta(),
    )


@router.post(
    "/admin/ingest/{job}",
    summary="Trigger an ingestion job (bearer token; used by external cron)",
    include_in_schema=True,
)
async def trigger_ingest(
    job: Literal["faa", "metar", "taf", "risk", "all"],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    token = get_settings().ingest_trigger_token
    if not token:
        raise HTTPException(status_code=404, detail="Not found")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied.encode(), token.encode()):
        raise HTTPException(status_code=401, detail="Invalid token")
    names = list(JOBS) if job == "all" else [job]
    results = []
    for name in names:
        summary = await JOBS[name](trigger="http")
        results.append(
            {
                "job": name,
                "run_id": summary.run_id,
                "status": summary.status,
                "error": summary.error,
            }
        )
    return {"data": results}


@router.post(
    "/ingest/tick",
    summary="Run only the ingestion jobs that are due (for external schedulers)",
)
async def ingest_tick() -> dict[str, object]:
    """Idempotent and lock-protected: extra calls cannot increase upstream polling."""
    return {"data": await tick()}
