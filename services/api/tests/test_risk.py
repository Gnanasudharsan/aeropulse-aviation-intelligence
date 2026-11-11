from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.services.risk import ForecastPeriodInput, RiskInputs, category_for, score

NOW = dt.datetime(2026, 11, 11, 15, 0, tzinfo=dt.UTC)


def period(
    h_from: int, h_to: int, cat: str = "VFR", wx: str | None = None, gust: int | None = None
) -> ForecastPeriodInput:
    return ForecastPeriodInput(
        NOW + dt.timedelta(hours=h_from), NOW + dt.timedelta(hours=h_to), cat, wx, gust, None
    )


def pts(result: object, key: str) -> float:
    return next(c.points for c in result.components if c.key == key)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("s", "cat"),
    [(0, "low"), (19.9, "low"), (20, "moderate"), (40, "elevated"), (60, "high"), (100, "high")],
)
def test_categories(s: float, cat: str) -> None:
    assert category_for(s) == cat


def test_quiet_airport_scores_low_with_explanations() -> None:
    r = score(
        RiskInputs(
            observed_risk="low", forecast_periods=(period(-1, 10),), historical_disruption_rate=0.1
        ),
        NOW,
    )
    assert r.score == 0 and r.category == "low"
    assert len(r.components) == 4 and all(c.detail for c in r.components)
    assert r.missing_inputs == []


def test_reported_ground_stop_dominates() -> None:
    r = score(
        RiskInputs(
            has_ground_stop=True,
            observed_risk="severe",
            forecast_periods=(period(0, 3, "LIFR"),),
            historical_disruption_rate=0.45,
        ),
        NOW,
    )
    assert (
        pts(r, "faa") == 45
        and pts(r, "observed") == 25
        and pts(r, "forecast") == 15
        and pts(r, "historical") == 15
    )
    assert r.score == 100 and r.category == "high"


def test_forecast_only_counts_next_six_hours_and_is_capped() -> None:
    later = score(RiskInputs(forecast_periods=(period(7, 12, "LIFR", "TSRA", 40),)), NOW)
    assert pts(later, "forecast") == 0
    soon = score(RiskInputs(forecast_periods=(period(1, 4, "LIFR", "TSRA", 40),)), NOW)
    assert pts(soon, "forecast") == 20  # 15 + 10 + 8 capped at 20


def test_historical_baseline_scaling() -> None:
    assert pts(score(RiskInputs(historical_disruption_rate=0.15), NOW), "historical") == 0
    assert pts(score(RiskInputs(historical_disruption_rate=0.25), NOW), "historical") == 6
    assert pts(score(RiskInputs(historical_disruption_rate=0.9), NOW), "historical") == 15


def test_missing_inputs_are_reported_not_imputed() -> None:
    r = score(RiskInputs(faa_current=False), NOW)
    assert set(r.missing_inputs) == {"faa", "observed", "forecast", "historical"}
    assert r.score == 0


def test_weather_alone_cannot_reach_high() -> None:
    r = score(
        RiskInputs(
            observed_risk="severe",
            forecast_periods=(period(0, 6, "LIFR", "TS", 40),),
            historical_disruption_rate=0.9,
        ),
        NOW,
    )
    assert (
        r.score == 60
    )  # 25 + 20 + 15: weather + history can reach "high" only with every factor maxed
    r2 = score(RiskInputs(observed_risk="severe", forecast_periods=(period(0, 6, "LIFR"),)), NOW)
    assert r2.category == "elevated"


# --------------------------------------------------------------------------- API (integration)


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.mark.integration
async def test_risk_job_persists_and_api_serves(client: TestClient) -> None:
    empty = client.get("/api/v1/risk/airports").json()["data"]
    assert empty["airports"] == [] and empty["is_stale"] is True

    from app.ingestion.jobs import run_risk_job

    summary = await run_risk_job(trigger="test")
    assert summary.status == "success" and summary.inserted == 50
    body = client.get("/api/v1/risk/airports").json()["data"]
    assert len(body["airports"]) == 50 and body["is_stale"] is False
    first = body["airports"][0]
    assert first["method_version"] == "rules-v1"
    assert {c["key"] for c in first["components"]} == {"faa", "observed", "forecast", "historical"}
    # Empty test DB: no FAA freshness, no weather, no forecast, no history -> all missing, score 0.
    assert set(first["missing_inputs"]) == {"faa", "observed", "forecast", "historical"}
    assert "not a confirmed delay" in body["disclaimer"]
    hist = client.get("/api/v1/risk/airports/JFK").json()["data"]
    assert hist["latest"]["airport_iata"] == "JFK" and len(hist["history"]) == 1
