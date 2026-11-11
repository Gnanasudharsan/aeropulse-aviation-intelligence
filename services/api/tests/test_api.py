"""API contract + integration tests (real PostgreSQL; test rows are inserted per test)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db, session_scope
from app.ingestion.persistence import mark_source
from app.main import create_app
from app.models import FaaAdvisory, OperationalEvent, WeatherObservation
from app.schemas import (
    AirportDetailOut,
    AirportSummaryOut,
    OperationalEventOut,
    OperationsSummaryOut,
    SourceFreshness,
    SystemStatusOut,
    WeatherOverviewOut,
)

pytestmark = pytest.mark.integration
NOW = dt.datetime.now(dt.UTC)


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def _obs(
    iata: str,
    icao: str,
    *,
    minutes_ago: int,
    cat: str = "VFR",
    vis: str = "10",
    gust: int | None = None,
) -> None:
    with session_scope() as s:
        s.add(
            WeatherObservation(
                station_icao=icao,
                observed_at=NOW - dt.timedelta(minutes=minutes_ago),
                raw_hash=f"h{minutes_ago:014d}",
                airport_iata=iata,
                raw_text=f"METAR {icao} TEST",
                flight_category=cat,
                visibility_sm=Decimal(vis),
                wind_speed_kt=12,
                wind_gust_kt=gust,
                ceiling_ft=None if cat == "VFR" else 400,
                cloud_layers=[{"cover": "OVC", "base_ft": 400}],
                temperature_c=10.0,
            )
        )


def _advisory(code: str, adv_type: str, *, cleared: bool = False, key: str | None = None) -> int:
    with session_scope() as s:
        a = FaaAdvisory(
            event_key=key or f"test:{code}:{adv_type}",
            source_feed="faa_json",
            airport_code=code,
            airport_iata=code,
            advisory_type=adv_type,
            scope="full",
            reason="TEST",
            details={},
            content_hash="x",
            first_seen_at=NOW - dt.timedelta(minutes=20),
            last_seen_at=NOW,
            starts_at=NOW - dt.timedelta(minutes=20),
            cleared_at=NOW if cleared else None,
        )
        s.add(a)
        s.flush()
        s.add(
            OperationalEvent(
                advisory_id=a.id,
                event_type="created",
                airport_code=code,
                advisory_type=adv_type,
                detected_at=NOW - dt.timedelta(minutes=20),
                changes={},
            )
        )
        if cleared:
            s.add(
                OperationalEvent(
                    advisory_id=a.id,
                    event_type="cleared",
                    airport_code=code,
                    advisory_type=adv_type,
                    detected_at=NOW,
                    changes={},
                )
            )
        return a.id


def _sources_fresh() -> None:
    with session_scope() as s:
        for src in ("faa_nas_status", "awc_metar", "awc_taf"):
            mark_source(s, src, success=True, at=NOW - dt.timedelta(minutes=2))


# --------------------------------------------------------------------------- empty database


def test_empty_database_degrades_gracefully(client: TestClient) -> None:
    summary = client.get("/api/v1/operations/summary")
    assert summary.status_code == 200
    data = OperationsSummaryOut.model_validate(summary.json()["data"])
    assert data.monitored_airports == 50
    assert data.active_ground_stops == 0
    assert data.faa_health == "unavailable" and data.weather_health == "unavailable"
    assert data.status_counts["unknown"] == 50  # never "normal" without evidence
    airports = client.get("/api/v1/airports").json()["data"]
    assert all(AirportSummaryOut.model_validate(a).status == "unknown" for a in airports)
    detail = AirportDetailOut.model_validate(client.get("/api/v1/airports/JFK").json()["data"])
    assert detail.latest_weather is None and detail.forecast is None
    assert client.get("/api/v1/operations/events").json()["meta"]["total"] == 0


# --------------------------------------------------------------------------- contract + values


def test_summary_values_correspond_to_database_rows(client: TestClient) -> None:
    _sources_fresh()
    _obs("JFK", "KJFK", minutes_ago=20)
    _obs("SFO", "KSFO", minutes_ago=15, cat="LIFR", vis="0.25")
    _obs("EWR", "KEWR", minutes_ago=10, cat="IFR", vis="2")
    _advisory("EWR", "ground_delay_program")
    _advisory("BOS", "ground_stop")
    _advisory("ORD", "departure_delay", cleared=True)

    data = OperationsSummaryOut.model_validate(
        client.get("/api/v1/operations/summary").json()["data"]
    )
    assert data.active_ground_stops == 1
    assert data.active_ground_delay_programs == 1
    assert data.active_reported_delays == 0  # ORD advisory was cleared
    assert data.airports_with_active_advisories == 2
    cats = {c.category: c.airports for c in data.flight_categories}
    assert cats == {"VFR": 1, "MVFR": 0, "IFR": 1, "LIFR": 1}
    assert data.status_counts["critical"] == 2  # EWR GDP, BOS GS
    assert data.status_counts["weather"] == 1  # SFO LIFR, no FAA program
    assert data.status_counts["normal"] == 1  # JFK
    assert data.changes_last_hour == 4
    assert data.faa_health == "healthy"

    sfo = AirportDetailOut.model_validate(client.get("/api/v1/airports/KSFO").json()["data"])
    assert sfo.iata_code == "SFO" and sfo.status == "weather" and sfo.weather_risk == "severe"
    assert sfo.latest_weather is not None and sfo.latest_weather.visibility_sm == 0.25


def test_stale_observations_are_labelled(client: TestClient) -> None:
    _sources_fresh()
    _obs("DEN", "KDEN", minutes_ago=200, cat="IFR")
    den = AirportDetailOut.model_validate(client.get("/api/v1/airports/DEN").json()["data"])
    assert den.weather_is_stale is True
    assert den.latest_weather is not None and den.latest_weather.is_stale is True
    assert den.status == "unknown" and den.weather_risk == "unknown"


def test_delayed_ingestion_surfaces_in_freshness(client: TestClient) -> None:
    with session_scope() as s:
        mark_source(s, "faa_nas_status", success=True, at=NOW - dt.timedelta(minutes=20))
        mark_source(s, "awc_metar", success=True, at=NOW - dt.timedelta(hours=8))
    fresh = {
        f["source"]: SourceFreshness.model_validate(f)
        for f in client.get("/api/v1/data-freshness").json()["data"]
    }
    assert fresh["faa_nas_status"].health == "delayed"
    assert fresh["awc_metar"].health == "unavailable"
    assert fresh["bts_ontime"].health == "unavailable"
    status = SystemStatusOut.model_validate(client.get("/api/v1/status").json()["data"])
    assert status.overall == "unavailable"


def test_airport_filters_and_search(client: TestClient) -> None:
    _sources_fresh()
    _obs("SFO", "KSFO", minutes_ago=5, cat="LIFR", vis="0.25")
    res = client.get("/api/v1/airports", params={"flight_category": "LIFR"}).json()
    assert [a["iata_code"] for a in res["data"]] == ["SFO"]
    res = client.get("/api/v1/airports", params={"q": "chicago"}).json()
    assert {a["iata_code"] for a in res["data"]} == {"ORD", "MDW"}
    res = client.get("/api/v1/airports", params={"state": "TX"}).json()
    assert {a["iata_code"] for a in res["data"]} == {"DFW", "IAH", "AUS", "DAL", "HOU", "SAT"}


@pytest.mark.parametrize(
    ("code", "status"), [("XYZ", 404), ("KXYZ", 404), ("J!K", 422), ("TOOLONG", 422)]
)
def test_invalid_airport_codes(client: TestClient, code: str, status: int) -> None:
    res = client.get(f"/api/v1/airports/{code}")
    assert res.status_code == status
    assert set(res.json()["error"]) == {"code", "message", "details"}


def test_events_pagination_filters_and_csv(client: TestClient) -> None:
    for i, code in enumerate(["BOS", "EWR", "JFK", "LGA"]):
        _advisory(code, "ground_stop", key=f"k{i}")
    page1 = client.get("/api/v1/operations/events", params={"page_size": 3}).json()
    assert (
        page1["meta"]["total"] == 4
        and page1["meta"]["total_pages"] == 2
        and len(page1["data"]) == 3
    )
    OperationalEventOut.model_validate(page1["data"][0])
    page2 = client.get("/api/v1/operations/events", params={"page_size": 3, "page": 2}).json()
    assert len(page2["data"]) == 1
    only_jfk = client.get("/api/v1/operations/events", params={"airport": "JFK"}).json()
    assert only_jfk["meta"]["total"] == 1
    csv_res = client.get("/api/v1/operations/events", params={"format": "csv"})
    assert csv_res.headers["content-type"].startswith("text/csv")
    lines = csv_res.text.strip().splitlines()
    assert lines[0].startswith("id,detected_at,event_type") and len(lines) == 5
    bad = client.get("/api/v1/operations/events", params={"page_size": 0})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    since = (NOW + dt.timedelta(hours=1)).isoformat()
    until = NOW.isoformat()
    assert (
        client.get("/api/v1/operations/events", params={"since": since, "until": until}).status_code
        == 422
    )


def test_advisory_detail_with_timeline(client: TestClient) -> None:
    adv_id = _advisory("ORD", "departure_delay", cleared=True)
    body = client.get(f"/api/v1/operations/advisories/{adv_id}").json()["data"]
    assert body["is_active"] is False
    assert [e["event_type"] for e in body["timeline"]] == ["created", "cleared"]
    assert client.get("/api/v1/operations/advisories/999999").status_code == 404
    active = client.get("/api/v1/operations/advisories", params={"state": "active"}).json()
    assert active["meta"]["total"] == 0
    everything = client.get("/api/v1/operations/advisories", params={"state": "all"}).json()
    assert everything["meta"]["total"] == 1


def test_weather_overview_and_trends(client: TestClient) -> None:
    _sources_fresh()
    _obs("SFO", "KSFO", minutes_ago=5, cat="LIFR", vis="0.25", gust=40)
    _obs("SFO", "KSFO", minutes_ago=65, cat="IFR", vis="2")
    _advisory("SFO", "ground_stop")
    ov = WeatherOverviewOut.model_validate(client.get("/api/v1/weather/overview").json()["data"])
    assert ov.lowest_visibility[0].airport == "SFO"
    assert ov.strongest_wind[0].value == 40
    assert ov.advisory_weather_overlap == ["SFO"]
    tr = client.get("/api/v1/weather/trends", params={"airports": "SFO,JFK", "hours": 3}).json()[
        "data"
    ]
    sfo = next(s for s in tr if s["airport"] == "SFO")
    assert sum(h["observations"] for h in sfo["hourly"]) == 2
    assert client.get("/api/v1/weather/trends", params={"airports": "ZZZ"}).status_code == 404
    assert (
        client.get("/api/v1/weather/trends", params={"airports": "A,B,C,D,E,F,G,H,I"}).status_code
        == 422
    )


def test_admin_trigger_requires_token(client: TestClient) -> None:
    assert client.post("/api/v1/admin/ingest/faa").status_code == 401
    assert (
        client.post(
            "/api/v1/admin/ingest/faa", headers={"Authorization": "Bearer nope"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/admin/ingest/bogus", headers={"Authorization": "Bearer test-token"}
        ).status_code
        == 422
    )


def test_cors_and_security_headers(client: TestClient) -> None:
    res = client.get("/api/v1/airports", headers={"Origin": "http://localhost:3000"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert res.headers["x-content-type-options"] == "nosniff"
    evil = client.get("/api/v1/airports", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in evil.headers


def test_openapi_documents_v1_endpoints(client: TestClient) -> None:
    paths = client.get("/api/openapi.json").json()["paths"]
    for p in [
        "/api/v1/health",
        "/api/v1/status",
        "/api/v1/airports",
        "/api/v1/airports/{code}",
        "/api/v1/airports/{code}/weather",
        "/api/v1/airports/{code}/advisories",
        "/api/v1/operations/summary",
        "/api/v1/operations/events",
        "/api/v1/weather/overview",
        "/api/v1/data-freshness",
    ]:
        assert p in paths


# --------------------------------------------------------------------------- failure modes


def test_database_connectivity_failure_returns_503(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    dead = sessionmaker(
        bind=create_engine(
            "postgresql+psycopg://x:y@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
        )
    )

    def broken_db() -> Iterator[object]:
        s = dead()
        try:
            yield s
        finally:
            s.close()

    import app.api.v1.system as system_module

    monkeypatch.setattr(system_module, "get_sessionmaker", lambda: dead)
    application = create_app()
    application.dependency_overrides[get_db] = broken_db
    with TestClient(application) as c:
        health = c.get("/api/v1/health")
        assert health.status_code == 503 and health.json()["database"] == "unavailable"
        res = c.get("/api/v1/operations/summary")
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "database_unavailable"
        assert "127.0.0.1" not in res.text  # no connection details leaked


def test_rate_limit(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3)
    with TestClient(create_app()) as c:
        codes = [c.get("/api/v1/data-freshness").status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200] and codes[3] == 429
        assert c.get("/api/v1/health").status_code == 200  # health exempt
