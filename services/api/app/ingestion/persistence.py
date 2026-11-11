"""Database writes for ingestion: bronze, run bookkeeping, idempotent silver upserts."""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingestion.faa import AdvisoryRecord, AirportConfigRecord
from app.ingestion.http import FetchResult
from app.ingestion.sources import SOURCES
from app.ingestion.weather import MetarRecord, TafRecord
from app.models import (
    Airport,
    AirportConfig,
    DataQualityResult,
    FaaAdvisory,
    IngestionRun,
    OperationalEvent,
    RawPayload,
    SourceStatus,
    WeatherForecast,
    WeatherForecastPeriod,
    WeatherObservation,
)

# --------------------------------------------------------------------------- runs & bronze


def start_run(session: Session, job: str, trigger: str) -> IngestionRun:
    run = IngestionRun(job=job, trigger=trigger, status="running", details={})
    session.add(run)
    session.flush()
    return run


def finish_run(
    session: Session,
    run_id: int,
    *,
    status: str,
    fetched: int = 0,
    inserted: int = 0,
    updated: int = 0,
    rejected: int = 0,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    run = session.get(IngestionRun, run_id)
    if run is None:
        return
    run.status = status
    run.finished_at = dt.datetime.now(dt.UTC)
    run.records_fetched = fetched
    run.records_inserted = inserted
    run.records_updated = updated
    run.records_rejected = rejected
    run.error_message = error[:2000] if error else None
    run.details = details or {}


def store_bronze(
    session: Session,
    *,
    source: str,
    run_id: int | None,
    fetch: FetchResult,
    published_at: dt.datetime | None = None,
    parse_status: str = "pending",
    parse_error: str | None = None,
) -> RawPayload:
    """Persist the raw payload. Identical consecutive payloads store only the checksum."""
    checksum = fetch.checksum
    previous = session.scalar(
        select(RawPayload.checksum_sha256)
        .where(RawPayload.source == source)
        .order_by(RawPayload.fetched_at.desc())
        .limit(1)
    )
    unchanged = previous == checksum
    row = RawPayload(
        source=source,
        ingestion_run_id=run_id,
        request_url=fetch.url,
        http_status=fetch.status,
        fetched_at=fetch.fetched_at,
        source_published_at=published_at or fetch.last_modified,
        content_type=(fetch.content_type or "")[:100] or None,
        byte_size=len(fetch.text.encode()),
        checksum_sha256=checksum,
        payload=None if unchanged else fetch.text,
        parse_status="unchanged" if unchanged and parse_status == "parsed" else parse_status,
        parse_error=parse_error,
    )
    session.add(row)
    session.flush()
    return row


def record_failed_fetch(
    session: Session, *, source: str, run_id: int | None, url: str, status: int | None, error: str
) -> None:
    session.add(
        RawPayload(
            source=source,
            ingestion_run_id=run_id,
            request_url=url,
            http_status=status,
            checksum_sha256="",
            payload=None,
            parse_status="fetch_failed",
            parse_error=error[:2000],
        )
    )


def purge_bronze(session: Session, older_than_days: int) -> int:
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=older_than_days)
    res = session.execute(delete(RawPayload).where(RawPayload.fetched_at < cutoff))
    return int(getattr(res, "rowcount", 0) or 0)


# --------------------------------------------------------------------------- source status


def ensure_source_rows(session: Session) -> None:
    for spec in SOURCES.values():
        stmt = pg_insert(SourceStatus).values(
            source=spec.key,
            display_name=spec.display_name,
            source_url=spec.url,
            expected_interval_seconds=spec.expected_interval_s,
            consecutive_failures=0,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SourceStatus.source],
            set_={
                "display_name": stmt.excluded.display_name,
                "source_url": stmt.excluded.source_url,
                "expected_interval_seconds": stmt.excluded.expected_interval_seconds,
            },
        )
        session.execute(stmt)


def mark_source(
    session: Session,
    source: str,
    *,
    success: bool,
    at: dt.datetime,
    error: str | None = None,
    published_at: dt.datetime | None = None,
    observation_at: dt.datetime | None = None,
    record_count: int | None = None,
) -> None:
    ensure_source_rows(session)
    row = session.get(SourceStatus, source)
    assert row is not None
    row.last_attempt_at = at
    if success:
        row.last_success_at = at
        row.consecutive_failures = 0
        row.last_error = None
        if published_at:
            row.last_source_published_at = published_at
        if observation_at and (
            row.last_observation_at is None or observation_at > row.last_observation_at
        ):
            row.last_observation_at = observation_at
        if record_count is not None:
            row.last_record_count = record_count
    else:
        row.last_failure_at = at
        row.consecutive_failures = (row.consecutive_failures or 0) + 1
        row.last_error = (error or "unknown error")[:1000]


def add_quality(
    session: Session,
    run_id: int,
    source: str,
    checks: Iterable[tuple[str, str, float | None, str | None, str | None]],
) -> list[dict[str, Any]]:
    out = []
    for name, status, value, threshold, message in checks:
        session.add(
            DataQualityResult(
                ingestion_run_id=run_id,
                source=source,
                check_name=name,
                status=status,
                observed_value=value,
                threshold=threshold,
                message=message,
            )
        )
        out.append({"check": name, "status": status, "value": value})
    return out


# --------------------------------------------------------------------------- airports


def monitored_airports(session: Session) -> list[Airport]:
    return list(
        session.scalars(select(Airport).where(Airport.is_monitored).order_by(Airport.iata_code))
    )


# --------------------------------------------------------------------------- weather


def upsert_metars(
    session: Session, records: Sequence[MetarRecord], icao_to_iata: dict[str, str]
) -> tuple[int, list[str]]:
    """Insert new observations; existing (station, observed_at, raw_hash) are skipped."""
    rows, unknown = [], []
    for r in records:
        iata = icao_to_iata.get(r.station_icao)
        if iata is None:
            unknown.append(r.station_icao)
            continue
        row = dataclasses.asdict(r)
        row["airport_iata"] = iata
        rows.append(row)
    if not rows:
        return 0, unknown
    stmt = (
        pg_insert(WeatherObservation)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["station_icao", "observed_at", "raw_hash"])
        .returning(WeatherObservation.station_icao)
    )
    inserted = len(session.execute(stmt).fetchall())
    return inserted, unknown


def upsert_tafs(
    session: Session, records: Sequence[TafRecord], icao_to_iata: dict[str, str]
) -> tuple[int, list[str]]:
    inserted, unknown = 0, []
    for r in records:
        iata = icao_to_iata.get(r.station_icao)
        if iata is None:
            unknown.append(r.station_icao)
            continue
        stmt = (
            pg_insert(WeatherForecast)
            .values(
                station_icao=r.station_icao,
                airport_iata=iata,
                issued_at=r.issued_at,
                bulletin_at=r.bulletin_at,
                valid_from=r.valid_from,
                valid_to=r.valid_to,
                raw_text=r.raw_text,
                raw_hash=r.raw_hash,
                is_amendment=r.is_amendment,
            )
            .on_conflict_do_nothing(constraint="uq_weather_forecasts_natural")
            .returning(WeatherForecast.id)
        )
        new_id = session.execute(stmt).scalar()
        if new_id is None:
            continue
        inserted += 1
        for p in r.periods:
            session.add(WeatherForecastPeriod(forecast_id=new_id, **dataclasses.asdict(p)))
    return inserted, unknown


# --------------------------------------------------------------------------- FAA advisories

_UPDATABLE = (
    "scope",
    "reason",
    "text",
    "starts_at",
    "ends_at",
    "source_updated_at",
    "avg_delay_minutes",
    "min_delay_minutes",
    "max_delay_minutes",
    "trend",
    "probability_of_extension",
    "advisory_url",
    "details",
)


@dataclasses.dataclass(slots=True)
class ReconcileStats:
    created: int = 0
    updated: int = 0
    cleared: int = 0
    unchanged: int = 0
    reopened: int = 0


def reconcile_advisories(
    session: Session,
    records: Sequence[AdvisoryRecord],
    *,
    run_id: int,
    now: dt.datetime,
    monitored_iata: set[str],
) -> ReconcileStats:
    """Apply one successful FAA poll.

    Active = present in the latest successful poll. Advisories absent from it are cleared.
    Every lifecycle transition is appended to ``operational_events``.
    """
    stats = ReconcileStats()
    incoming: dict[str, AdvisoryRecord] = {}
    for rec in records:
        incoming[rec.event_key] = rec

    active = list(session.scalars(select(FaaAdvisory).where(FaaAdvisory.cleared_at.is_(None))))
    by_key = {a.event_key: a for a in active}
    by_airport_type: dict[tuple[str, str], list[FaaAdvisory]] = {}
    for a in active:
        by_airport_type.setdefault((a.airport_code, a.advisory_type), []).append(a)
    cleared_existing = {
        a.event_key: a
        for a in session.scalars(
            select(FaaAdvisory).where(
                FaaAdvisory.event_key.in_(list(incoming)), FaaAdvisory.cleared_at.is_not(None)
            )
        )
    }

    matched: set[int] = set()
    for key, rec in incoming.items():
        adv = by_key.get(key)
        if adv is None and rec.source_feed == "faa_xml":
            # Fallback feed has no ids: match an active advisory of the same airport+type.
            # The XML feed lists full and NOTAM closures together, so treat them as one family.
            types = (
                ("closure_notam", "airport_closure")
                if rec.advisory_type in {"closure_notam", "airport_closure"}
                else (rec.advisory_type,)
            )
            candidates = [c for t in types for c in by_airport_type.get((rec.airport_code, t), [])]
            for cand in candidates:
                if cand.id not in matched and (
                    rec.starts_at is None
                    or cand.starts_at is None
                    or cand.starts_at == rec.starts_at
                ):
                    adv = cand
                    break
        if adv is None and key in cleared_existing:
            adv = cleared_existing[key]
            adv.cleared_at = None
            stats.reopened += 1
            _event(session, adv, "reopened", run_id, now, {})
        if adv is None:
            adv = FaaAdvisory(
                event_key=key,
                source_event_id=rec.source_event_id,
                source_feed=rec.source_feed,
                airport_code=rec.airport_code,
                airport_iata=rec.airport_code if rec.airport_code in monitored_iata else None,
                advisory_type=rec.advisory_type,
                content_hash=rec.content_hash,
                first_seen_at=now,
                last_seen_at=now,
                **{f: getattr(rec, f) for f in _UPDATABLE},
            )
            session.add(adv)
            session.flush()
            stats.created += 1
            _event(session, adv, "created", run_id, now, {"type": rec.advisory_type})
        else:
            adv.last_seen_at = now
            if adv.source_feed != rec.source_feed:
                # Cross-feed match (XML fallback confirming a JSON advisory): presence only.
                stats.unchanged += 1
            elif adv.content_hash != rec.content_hash:
                changes = {}
                for f in _UPDATABLE:
                    old, new = getattr(adv, f), getattr(rec, f)
                    if f not in {"details", "source_updated_at"} and old != new and new is not None:
                        changes[f] = {"from": _jsonable(old), "to": _jsonable(new)}
                        setattr(adv, f, new)
                adv.source_updated_at = rec.source_updated_at or adv.source_updated_at
                adv.details = rec.details or adv.details
                adv.content_hash = rec.content_hash
                if changes:
                    stats.updated += 1
                    _event(session, adv, "updated", run_id, now, changes)
                else:
                    stats.unchanged += 1
            else:
                stats.unchanged += 1
        matched.add(adv.id)

    for adv in active:
        if adv.id not in matched:
            adv.cleared_at = now
            stats.cleared += 1
            _event(session, adv, "cleared", run_id, now, {})
    return stats


def _jsonable(v: Any) -> Any:
    return v.isoformat() if isinstance(v, dt.datetime) else v


def _event(
    session: Session,
    adv: FaaAdvisory,
    kind: str,
    run_id: int,
    now: dt.datetime,
    changes: dict[str, Any],
) -> None:
    session.add(
        OperationalEvent(
            advisory_id=adv.id,
            event_type=kind,
            airport_code=adv.airport_code,
            advisory_type=adv.advisory_type,
            detected_at=now,
            source_updated_at=adv.source_updated_at,
            ingestion_run_id=run_id,
            changes=changes,
        )
    )


def upsert_airport_configs(session: Session, configs: Sequence[AirportConfigRecord]) -> int:
    if not configs:
        return 0
    rows = [dataclasses.asdict(c) for c in configs]
    stmt = (
        pg_insert(AirportConfig)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["airport_code", "source_timestamp"])
        .returning(AirportConfig.airport_code)
    )
    return len(session.execute(stmt).fetchall())
