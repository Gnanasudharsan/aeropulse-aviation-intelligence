"""Integration tests: ingestion jobs against a real PostgreSQL, upstreams mocked with respx."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import session_scope
from app.ingestion.jobs import run_faa_job, run_metar_job, run_taf_job
from app.models import (
    DataQualityResult,
    FaaAdvisory,
    IngestionRun,
    OperationalEvent,
    RawPayload,
    SourceStatus,
    WeatherForecast,
    WeatherObservation,
)

pytestmark = pytest.mark.integration
FIX = Path(__file__).parent / "fixtures"
S = get_settings()
REAL_JSON = (FIX / "real_faa_airport_events.json").read_text()
REAL_XML = (FIX / "real_faa_status.xml").read_text()
METARS = (FIX / "real_awc_metar.json").read_text()
TAFS = (FIX / "real_awc_taf.json").read_text()


def _faa(json_resp: httpx.Response | Exception, xml_resp: httpx.Response | Exception) -> None:
    for url, resp in ((S.faa_airport_events_url, json_resp), (S.faa_status_xml_url, xml_resp)):
        route = respx.get(url)
        if isinstance(resp, Exception):
            route.mock(side_effect=resp)
        else:
            route.mock(return_value=resp)


def _count(model: type, *where: object) -> int:
    with session_scope() as s:
        return int(s.scalar(select(func.count()).select_from(model).where(*where)) or 0)


@respx.mock
async def test_faa_success_lifecycle_created_then_cleared(db: None) -> None:
    _faa(httpx.Response(200, text=REAL_JSON), httpx.Response(200, text=REAL_XML))
    first = await run_faa_job(trigger="test")
    assert first.status == "success" and first.inserted == 4
    assert _count(FaaAdvisory, FaaAdvisory.cleared_at.is_(None)) == 4
    assert _count(OperationalEvent, OperationalEvent.event_type == "created") == 4

    # Next poll: LAX no longer reported -> cleared, the rest unchanged.
    remaining = [e for e in json.loads(REAL_JSON) if e["airportId"] != "LAX"]
    respx.reset()
    _faa(httpx.Response(200, text=json.dumps(remaining)), httpx.Response(200, text=REAL_XML))
    second = await run_faa_job(trigger="test")
    assert second.inserted == 0 and second.updated == 1
    with session_scope() as s:
        lax = s.scalar(select(FaaAdvisory).where(FaaAdvisory.airport_code == "LAX"))
        assert lax is not None and lax.cleared_at is not None
    assert _count(OperationalEvent, OperationalEvent.event_type == "cleared") == 1


@respx.mock
async def test_faa_feed_unavailable_preserves_last_good_data(db: None) -> None:
    _faa(httpx.Response(200, text=REAL_JSON), httpx.Response(200, text=REAL_XML))
    await run_faa_job(trigger="test")
    respx.reset()
    _faa(httpx.Response(503), httpx.ConnectError("down"))
    res = await run_faa_job(trigger="test")
    assert res.status == "failed"
    assert _count(FaaAdvisory, FaaAdvisory.cleared_at.is_(None)) == 4  # nothing cleared
    with session_scope() as s:
        st = s.get(SourceStatus, "faa_nas_status")
        assert st is not None and st.consecutive_failures == 1 and st.last_success_at is not None
        run = s.get(IngestionRun, res.run_id)
        assert run is not None and run.status == "failed" and run.error_message
    assert _count(RawPayload, RawPayload.parse_status == "fetch_failed") == 2


@respx.mock
async def test_faa_json_malformed_falls_back_to_xml_without_duplicates(db: None) -> None:
    _faa(httpx.Response(200, text=REAL_JSON), httpx.Response(200, text=REAL_XML))
    await run_faa_job(trigger="test")
    respx.reset()
    _faa(httpx.Response(200, text="<html>maintenance</html>"), httpx.Response(200, text=REAL_XML))
    res = await run_faa_job(trigger="test")
    assert res.status == "partial"
    assert res.details["feed_used"] == "xml_fallback"
    assert res.inserted == 0  # XML records matched existing JSON advisories
    assert _count(FaaAdvisory, FaaAdvisory.cleared_at.is_(None)) == 4
    with session_scope() as s:
        checks = {
            c.check_name: c.status
            for c in s.scalars(
                select(DataQualityResult).where(DataQualityResult.ingestion_run_id == res.run_id)
            )
        }
    assert checks["feed_primary_available"] == "warn"


@respx.mock
async def test_metar_duplicates_are_idempotent(db: None) -> None:
    respx.get(url__startswith=f"{S.awc_base_url}/metar").mock(
        return_value=httpx.Response(200, text=METARS)
    )
    first = await run_metar_job(trigger="test")
    second = await run_metar_job(trigger="test")
    assert first.inserted == len(json.loads(METARS))
    assert second.inserted == 0
    assert _count(WeatherObservation) == first.inserted
    # identical payload stored once; second bronze row is checksum-only
    assert _count(RawPayload, RawPayload.parse_status == "unchanged") == 1


@respx.mock
async def test_metar_partial_coverage_is_flagged(db: None) -> None:
    respx.get(url__startswith=f"{S.awc_base_url}/metar").mock(
        return_value=httpx.Response(200, text=METARS)
    )
    res = await run_metar_job(trigger="test")
    # fixture covers 7 of 50 monitored stations
    assert res.status == "partial"
    assert res.details["coverage"] == pytest.approx(7 / 50)
    with session_scope() as s:
        cov = s.scalar(
            select(DataQualityResult).where(
                DataQualityResult.ingestion_run_id == res.run_id,
                DataQualityResult.check_name == "station_coverage",
            )
        )
        assert cov is not None and cov.status == "fail"


@respx.mock
async def test_weather_timeout_marks_source_failed_and_keeps_data(db: None) -> None:
    route = respx.get(url__startswith=f"{S.awc_base_url}/metar")
    route.mock(return_value=httpx.Response(200, text=METARS))
    await run_metar_job(trigger="test")
    before = _count(WeatherObservation)
    route.mock(side_effect=httpx.ReadTimeout("slow"))
    res = await run_metar_job(trigger="test")
    assert res.status == "failed" and "ReadTimeout" in (res.error or "")
    assert _count(WeatherObservation) == before
    with session_scope() as s:
        st = s.get(SourceStatus, "awc_metar")
        assert st is not None and st.consecutive_failures == 1


@respx.mock
async def test_metar_malformed_response(db: None) -> None:
    respx.get(url__startswith=f"{S.awc_base_url}/metar").mock(
        return_value=httpx.Response(200, text="{oops")
    )
    res = await run_metar_job(trigger="test")
    assert res.status == "failed" and "ParseError" in (res.error or "")


@respx.mock
async def test_taf_ingestion_stores_forecasts_and_periods(db: None) -> None:
    respx.get(url__startswith=f"{S.awc_base_url}/taf").mock(
        return_value=httpx.Response(200, text=TAFS)
    )
    res = await run_taf_job(trigger="test")
    assert res.inserted == len(json.loads(TAFS))
    again = await run_taf_job(trigger="test")
    assert again.inserted == 0
    with session_scope() as s:
        fc = s.scalars(select(WeatherForecast)).first()
        assert fc is not None and len(fc.periods) > 0
