"""Ingestion jobs. Each job is a plain coroutine so it can be driven by the APScheduler
worker, the CLI, an authenticated HTTP trigger, or wrapped by an orchestrator later.

Every run writes an ``ingestion_runs`` row, bronze payload(s), data-quality results and
updates ``source_status``. A failed run never deletes or overwrites the last good data.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.ingestion import faa as faa_parser
from app.ingestion import persistence as db
from app.ingestion import weather as wx_parser
from app.ingestion.http import FetchError, FetchResult, build_client, fetch_text
from app.ingestion.sources import FEED_FAA_JSON, FEED_FAA_XML, FEED_METAR, FEED_TAF

log = get_logger(__name__)

METAR_LOOKBACK_HOURS = 3  # re-request recent history so a missed run is back-filled
OBS_STALE_SECONDS = 2 * 3600


@dataclass(slots=True)
class RunSummary:
    job: str
    run_id: int
    status: str
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _start(job: str, trigger: str) -> int:
    with session_scope() as s:
        db.ensure_source_rows(s)
        return db.start_run(s, job, trigger).id


def _fail(
    job: str, run_id: int, source: str, exc: Exception, details: dict[str, Any]
) -> RunSummary:
    msg = f"{type(exc).__name__}: {exc}"
    with session_scope() as s:
        db.mark_source(s, source, success=False, at=_now(), error=msg)
        db.finish_run(s, run_id, status="failed", error=msg, details=details)
    log.error("ingestion_failed", job=job, run_id=run_id, error=msg)
    return RunSummary(job=job, run_id=run_id, status="failed", error=msg, details=details)


def _record_fetch_failure(feed: str, run_id: int, url: str, exc: FetchError) -> None:
    with session_scope() as ses:
        db.record_failed_fetch(
            ses, source=feed, run_id=run_id, url=url, status=exc.status, error=str(exc)
        )


# --------------------------------------------------------------------------- FAA


async def run_faa_job(
    client: httpx.AsyncClient | None = None, trigger: str = "schedule"
) -> RunSummary:
    s = get_settings()
    run_id = _start("faa", trigger)
    own_client = client is None
    client = client or build_client()
    details: dict[str, Any] = {}
    try:
        json_res, xml_res = await asyncio.gather(
            fetch_text(client, s.faa_airport_events_url),
            fetch_text(client, s.faa_status_xml_url),
            return_exceptions=True,
        )
    finally:
        if own_client:
            await client.aclose()

    parsed: faa_parser.FaaParseResult | None = None
    feed_used: str | None = None
    errors: dict[str, str] = {}
    xml_parsed: faa_parser.FaaParseResult | None = None

    if isinstance(xml_res, FetchResult):
        try:
            xml_parsed = faa_parser.parse_airport_status_xml(xml_res.text)
        except faa_parser.ParseError as exc:
            errors[FEED_FAA_XML] = f"parse: {exc}"
    else:
        errors[FEED_FAA_XML] = f"fetch: {xml_res}"

    if isinstance(json_res, FetchResult):
        try:
            parsed, feed_used = faa_parser.parse_airport_events_json(json_res.text), "json"
        except faa_parser.ParseError as exc:
            errors[FEED_FAA_JSON] = f"parse: {exc}"
    else:
        errors[FEED_FAA_JSON] = f"fetch: {json_res}"

    if parsed is None and xml_parsed is not None:
        parsed, feed_used = xml_parsed, "xml_fallback"

    published_at = xml_parsed.published_at if xml_parsed else None
    details.update(feed_used=feed_used, errors=errors)
    now = _now()

    def persist() -> RunSummary:
        # Bronze is committed on its own so failed fetches stay auditable even if the run fails.
        with session_scope() as ses:
            for feed, res, ok in (
                (FEED_FAA_JSON, json_res, FEED_FAA_JSON not in errors),
                (FEED_FAA_XML, xml_res, FEED_FAA_XML not in errors),
            ):
                if isinstance(res, FetchResult):
                    db.store_bronze(
                        ses,
                        source=feed,
                        run_id=run_id,
                        fetch=res,
                        published_at=published_at if feed == FEED_FAA_XML else None,
                        parse_status="parsed" if ok else "parse_failed",
                        parse_error=None if ok else errors.get(feed),
                    )
                else:
                    err = res if isinstance(res, FetchError) else None
                    db.record_failed_fetch(
                        ses,
                        source=feed,
                        run_id=run_id,
                        url=err.url if err else "",
                        status=err.status if err else None,
                        error=errors.get(feed, "unknown"),
                    )
        if parsed is None:
            raise FetchError("; ".join(f"{k}: {v}" for k, v in errors.items()))

        with session_scope() as ses:
            monitored = {a.iata_code for a in db.monitored_airports(ses)}
            stats = db.reconcile_advisories(
                ses, parsed.advisories, run_id=run_id, now=now, monitored_iata=monitored
            )
            configs = db.upsert_airport_configs(ses, parsed.configs)
            airports = {a.airport_code for a in parsed.advisories}
            missing_ts = sum(
                1
                for a in parsed.advisories
                if a.starts_at is None
                and a.advisory_type in {"ground_stop", "ground_delay_program"}
            )
            checks = [
                (
                    "feed_primary_available",
                    "pass" if feed_used == "json" else "warn",
                    1.0 if feed_used == "json" else 0.0,
                    "json",
                    f"feed used: {feed_used}",
                ),
                (
                    "records_rejected",
                    "pass" if not parsed.rejected else "warn",
                    float(len(parsed.rejected)),
                    "0",
                    "; ".join(parsed.rejected[:5]) or None,
                ),
                (
                    "advisories_missing_start",
                    "pass" if not missing_ts else "warn",
                    float(missing_ts),
                    "0",
                    None,
                ),
                (
                    "non_monitored_airports",
                    "pass",
                    float(len(airports - monitored)),
                    None,
                    ",".join(sorted(airports - monitored))[:500] or None,
                ),
            ]
            if published_at:
                age = (now - published_at).total_seconds()
                checks.append(
                    ("xml_publication_age_s", "pass" if age < 1800 else "warn", age, "<1800", None)
                )
            details["quality"] = db.add_quality(ses, run_id, "faa_nas_status", checks)
            details["reconcile"] = dataclasses.asdict(stats)
            details["configs_inserted"] = configs
            db.mark_source(
                ses,
                "faa_nas_status",
                success=True,
                at=now,
                published_at=published_at or parsed.published_at,
                record_count=len(parsed.advisories),
            )
            status = "success" if feed_used == "json" and not parsed.rejected else "partial"
            db.finish_run(
                ses,
                run_id,
                status=status,
                fetched=len(parsed.advisories),
                inserted=stats.created,
                updated=stats.updated + stats.cleared,
                rejected=len(parsed.rejected),
                details=details,
            )
            return RunSummary(
                "faa",
                run_id,
                status,
                len(parsed.advisories),
                stats.created,
                stats.updated + stats.cleared,
                len(parsed.rejected),
                None,
                details,
            )

    try:
        summary = await asyncio.to_thread(persist)
    except Exception as exc:
        return _fail("faa", run_id, "faa_nas_status", exc, details)
    log.info(
        "ingestion_complete",
        job="faa",
        run_id=run_id,
        status=summary.status,
        fetched=summary.fetched,
        created=summary.inserted,
        changed=summary.updated,
    )
    return summary


# --------------------------------------------------------------------------- METAR / TAF


def _station_map() -> tuple[dict[str, str], list[str]]:
    with session_scope() as s:
        airports = db.monitored_airports(s)
        return {a.icao_code: a.iata_code for a in airports}, [a.icao_code for a in airports]


async def run_metar_job(
    client: httpx.AsyncClient | None = None, trigger: str = "schedule"
) -> RunSummary:
    s = get_settings()
    run_id = _start("metar", trigger)
    icao_to_iata, stations = _station_map()
    url = f"{s.awc_base_url}/metar"
    params = {"ids": ",".join(stations), "format": "json", "hours": str(METAR_LOOKBACK_HOURS)}
    details: dict[str, Any] = {"stations_requested": len(stations)}
    own_client = client is None
    client = client or build_client()
    try:
        fetch = await fetch_text(client, url, params=params)
        parsed = wx_parser.parse_metars(fetch.text)
    except (FetchError, wx_parser.ParseError) as exc:
        if isinstance(exc, FetchError):
            await asyncio.to_thread(_record_fetch_failure, FEED_METAR, run_id, url, exc)
        return _fail("metar", run_id, "awc_metar", exc, details)
    finally:
        if own_client:
            await client.aclose()

    now = _now()

    def persist() -> RunSummary:
        with session_scope() as ses:
            db.store_bronze(
                ses, source=FEED_METAR, run_id=run_id, fetch=fetch, parse_status="parsed"
            )
            inserted, unknown = db.upsert_metars(ses, parsed.records, icao_to_iata)
            latest: dict[str, dt.datetime] = {}
            for r in parsed.records:
                if r.station_icao in icao_to_iata:
                    latest[r.station_icao] = max(
                        latest.get(r.station_icao, r.observed_at), r.observed_at
                    )
            coverage = len(latest) / max(len(stations), 1)
            stale = [
                st for st, t in latest.items() if (now - t).total_seconds() > OBS_STALE_SECONDS
            ]
            duplicates = len(parsed.records) - len(unknown) - inserted
            checks = [
                (
                    "station_coverage",
                    "pass" if coverage >= 0.9 else "warn" if coverage >= 0.5 else "fail",
                    round(coverage, 3),
                    ">=0.9",
                    ",".join(sorted(set(stations) - set(latest))) or None,
                ),
                (
                    "stale_observations",
                    "pass" if not stale else "warn",
                    float(len(stale)),
                    "0",
                    ",".join(stale) or None,
                ),
                (
                    "records_rejected",
                    "pass" if not parsed.rejected else "warn",
                    float(len(parsed.rejected)),
                    "0",
                    "; ".join(parsed.rejected[:5]) or None,
                ),
                (
                    "duplicates_skipped",
                    "pass",
                    float(duplicates),
                    None,
                    "already-stored observations re-delivered by lookback window",
                ),
                (
                    "unknown_stations",
                    "pass" if not unknown else "warn",
                    float(len(unknown)),
                    "0",
                    ",".join(sorted(set(unknown))) or None,
                ),
            ]
            details["quality"] = db.add_quality(ses, run_id, "awc_metar", checks)
            details.update(inserted=inserted, duplicates=duplicates, coverage=coverage)
            db.mark_source(
                ses,
                "awc_metar",
                success=True,
                at=now,
                published_at=max(
                    (r.source_published_at for r in parsed.records if r.source_published_at),
                    default=None,
                ),
                observation_at=max(latest.values(), default=None),
                record_count=len(parsed.records),
            )
            status = "success" if coverage >= 0.9 and not parsed.rejected else "partial"
            db.finish_run(
                ses,
                run_id,
                status=status,
                fetched=len(parsed.records),
                inserted=inserted,
                rejected=len(parsed.rejected),
                details=details,
            )
            return RunSummary(
                "metar",
                run_id,
                status,
                len(parsed.records),
                inserted,
                0,
                len(parsed.rejected),
                None,
                details,
            )

    try:
        summary = await asyncio.to_thread(persist)
    except Exception as exc:
        return _fail("metar", run_id, "awc_metar", exc, details)
    log.info(
        "ingestion_complete",
        job="metar",
        run_id=run_id,
        status=summary.status,
        fetched=summary.fetched,
        inserted=summary.inserted,
    )
    return summary


async def run_taf_job(
    client: httpx.AsyncClient | None = None, trigger: str = "schedule"
) -> RunSummary:
    s = get_settings()
    run_id = _start("taf", trigger)
    icao_to_iata, stations = _station_map()
    url = f"{s.awc_base_url}/taf"
    params = {"ids": ",".join(stations), "format": "json"}
    details: dict[str, Any] = {"stations_requested": len(stations)}
    own_client = client is None
    client = client or build_client()
    try:
        fetch = await fetch_text(client, url, params=params)
        parsed = wx_parser.parse_tafs(fetch.text)
    except (FetchError, wx_parser.ParseError) as exc:
        if isinstance(exc, FetchError):
            await asyncio.to_thread(_record_fetch_failure, FEED_TAF, run_id, url, exc)
        return _fail("taf", run_id, "awc_taf", exc, details)
    finally:
        if own_client:
            await client.aclose()

    now = _now()

    def persist() -> RunSummary:
        with session_scope() as ses:
            db.store_bronze(ses, source=FEED_TAF, run_id=run_id, fetch=fetch, parse_status="parsed")
            inserted, _unknown = db.upsert_tafs(ses, parsed.records, icao_to_iata)
            covered = {r.station_icao for r in parsed.records}
            coverage = len(covered & set(stations)) / max(len(stations), 1)
            checks = [
                (
                    "station_coverage",
                    "pass" if coverage >= 0.9 else "warn" if coverage >= 0.5 else "fail",
                    round(coverage, 3),
                    ">=0.9",
                    ",".join(sorted(set(stations) - covered)) or None,
                ),
                (
                    "records_rejected",
                    "pass" if not parsed.rejected else "warn",
                    float(len(parsed.rejected)),
                    "0",
                    "; ".join(parsed.rejected[:5]) or None,
                ),
            ]
            details["quality"] = db.add_quality(ses, run_id, "awc_taf", checks)
            details.update(inserted=inserted, coverage=coverage)
            db.mark_source(
                ses,
                "awc_taf",
                success=True,
                at=now,
                published_at=max((r.issued_at for r in parsed.records), default=None),
                observation_at=max((r.issued_at for r in parsed.records), default=None),
                record_count=len(parsed.records),
            )
            status = "success" if coverage >= 0.9 and not parsed.rejected else "partial"
            db.finish_run(
                ses,
                run_id,
                status=status,
                fetched=len(parsed.records),
                inserted=inserted,
                rejected=len(parsed.rejected),
                details=details,
            )
            return RunSummary(
                "taf",
                run_id,
                status,
                len(parsed.records),
                inserted,
                0,
                len(parsed.rejected),
                None,
                details,
            )

    try:
        summary = await asyncio.to_thread(persist)
    except Exception as exc:
        return _fail("taf", run_id, "awc_taf", exc, details)
    log.info(
        "ingestion_complete",
        job="taf",
        run_id=run_id,
        status=summary.status,
        fetched=summary.fetched,
        inserted=summary.inserted,
    )
    return summary


async def run_risk_job(
    client: httpx.AsyncClient | None = None, trigger: str = "schedule"
) -> RunSummary:
    """Compute the rules-based risk indicator (and model output, if validated) for all airports."""
    from app.services import risk_job

    run_id = _start("risk", trigger)

    def compute() -> RunSummary:
        now = _now()
        with session_scope() as ses:
            rows = risk_job.compute_all(ses, now)
            n = risk_job.persist(ses, rows)
            details = {
                "categories": {
                    c: sum(1 for r in rows if r["category"] == c)
                    for c in ("low", "moderate", "elevated", "high")
                },
                "model_scored": sum(1 for r in rows if r["model_probability"] is not None),
            }
            db.finish_run(
                ses, run_id, status="success", fetched=len(rows), inserted=n, details=details
            )
            return RunSummary("risk", run_id, "success", len(rows), n, 0, 0, None, details)

    try:
        summary = await asyncio.to_thread(compute)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        with session_scope() as ses:
            db.finish_run(ses, run_id, status="failed", error=msg)
        log.error("risk_failed", run_id=run_id, error=msg)
        return RunSummary("risk", run_id, "failed", error=msg)
    log.info("risk_complete", run_id=run_id, scored=summary.inserted)
    return summary


def run_maintenance(trigger: str = "schedule") -> int:
    """Purge bronze payloads past retention; recorded as an ingestion run ("purge")."""
    with session_scope() as s:
        run = db.start_run(s, "purge", trigger)
        purged = db.purge_bronze(s, get_settings().bronze_retention_days)
        db.finish_run(s, run.id, status="success", updated=purged, details={"purged": purged})
    log.info("bronze_purged", rows=purged)
    return purged


JOBS = {"faa": run_faa_job, "metar": run_metar_job, "taf": run_taf_job, "risk": run_risk_job}
