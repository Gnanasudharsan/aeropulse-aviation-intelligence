"""The public tick endpoint runs only due jobs and cannot amplify upstream polling."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.session import get_engine, session_scope
from app.ingestion.tick import LOCK_KEY
from app.main import create_app
from app.models import IngestionRun

pytestmark = pytest.mark.integration
FIX = Path(__file__).parent / "fixtures"
S = get_settings()


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def _mock_upstreams() -> None:
    respx.get(S.faa_airport_events_url).mock(
        return_value=httpx.Response(200, text=(FIX / "real_faa_airport_events.json").read_text())
    )
    respx.get(S.faa_status_xml_url).mock(
        return_value=httpx.Response(200, text=(FIX / "real_faa_status.xml").read_text())
    )
    respx.get(url__startswith=f"{S.awc_base_url}/metar").mock(
        return_value=httpx.Response(200, text=(FIX / "real_awc_metar.json").read_text())
    )
    respx.get(url__startswith=f"{S.awc_base_url}/taf").mock(
        return_value=httpx.Response(200, text=(FIX / "real_awc_taf.json").read_text())
    )
    respx.route(host="testserver").pass_through()


def _runs() -> dict[str, int]:
    with session_scope() as s:
        return dict(
            s.execute(select(IngestionRun.job, func.count()).group_by(IngestionRun.job)).all()
        )


@respx.mock
def test_tick_runs_due_jobs_once(client: TestClient) -> None:
    _mock_upstreams()
    first = client.post("/api/v1/ingest/tick").json()["data"]
    assert [r["job"] for r in first["ran"]] == ["faa", "metar", "taf", "risk", "purge"]
    assert _runs() == {"faa": 1, "metar": 1, "taf": 1, "risk": 1, "purge": 1}
    # Immediately again: nothing is due, so no upstream calls and no new runs.
    second = client.post("/api/v1/ingest/tick").json()["data"]
    assert second["ran"] == []
    assert _runs() == {"faa": 1, "metar": 1, "taf": 1, "risk": 1, "purge": 1}


def test_tick_skips_when_another_tick_holds_the_lock(client: TestClient) -> None:
    with get_engine().connect() as conn:
        assert conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})
        try:
            body = client.post("/api/v1/ingest/tick").json()["data"]
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
    assert body == {"ran": [], "skipped": "another tick is running"}
    assert _runs() == {}


def test_rate_limit_uses_forwarded_client_ip_when_trusted(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 1)
    monkeypatch.setattr(get_settings(), "trust_forwarded_for", True)
    with TestClient(create_app()) as c:
        a = {"X-Forwarded-For": "203.0.113.1"}
        b = {"X-Forwarded-For": "203.0.113.2, 10.0.0.1"}
        assert c.get("/api/v1/data-freshness", headers=a).status_code == 200
        assert c.get("/api/v1/data-freshness", headers=a).status_code == 429
        assert c.get("/api/v1/data-freshness", headers=b).status_code == 200  # different client
