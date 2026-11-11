"""Historical analytics: rates are recomputed from additive sums; coverage is honest."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import session_scope
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def _day(
    airport: str,
    day: dt.date,
    direction: str,
    flights: int,
    den: int,
    ontime: int,
    delay_sum: int,
    cancelled: int = 0,
) -> None:
    with session_scope() as s:
        s.execute(
            text(
                "INSERT INTO airport_performance_daily (airport_iata, flight_date, direction, flights, "
                "cancelled, ontime_den, ontime_num, delayed_15, delay_sum_min, weather_delay_min) "
                "VALUES (:a, :d, :dir, :f, :c, :den, :on, :late, :sum, 30)"
            ),
            {
                "a": airport,
                "d": day,
                "dir": direction,
                "f": flights,
                "c": cancelled,
                "den": den,
                "on": ontime,
                "late": den - ontime,
                "sum": delay_sum,
            },
        )
        s.execute(
            text(
                "INSERT INTO historical_loads (year_month, source_file, source_sha256, rows_read, rows_monitored) "
                "VALUES (:m, 'test.zip', 'x', 1, 1) ON CONFLICT DO NOTHING"
            ),
            {"m": day.replace(day=1)},
        )


def test_no_historical_data_is_reported_as_unavailable(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/overview").json()["data"]
    assert body["available"] is False
    assert body["totals"] is None and body["coverage"]["months_loaded"] == 0


def test_rates_use_additive_sums_not_average_of_averages(client: TestClient) -> None:
    # JFK: 10 flights, 9 on time of 10 measured. LGA: 100 flights, 50 on time of 100.
    _day("JFK", dt.date(2025, 6, 1), "arrival", 10, 10, 9, 20)
    _day("LGA", dt.date(2025, 6, 1), "arrival", 100, 100, 50, 1000, cancelled=0)
    body = client.get(
        "/api/v1/analytics/overview", params={"start": "2025-06", "end": "2025-06"}
    ).json()["data"]
    assert body["available"] is True
    assert body["totals"]["flights"] == 110
    assert body["totals"]["ontime_rate"] == pytest.approx(59 / 110, abs=1e-4)  # not (0.9 + 0.5) / 2
    assert body["totals"]["avg_delay_min"] == pytest.approx(1020 / 110, abs=0.01)
    assert [a["airport"] for a in body["airports"]] == ["JFK", "LGA"]
    assert body["airports"][0]["rank_ontime"] == 1


def test_direction_filter_and_airport_history_with_network_comparison(client: TestClient) -> None:
    _day("JFK", dt.date(2025, 6, 2), "arrival", 10, 10, 5, 100)
    _day("JFK", dt.date(2025, 6, 2), "departure", 10, 10, 10, 0)
    _day("BOS", dt.date(2025, 6, 2), "arrival", 10, 10, 10, 0)
    dep = client.get("/api/v1/airports/JFK/history", params={"direction": "departure"}).json()[
        "data"
    ]
    assert dep["totals"]["ontime_rate"] == 1.0
    arr = client.get("/api/v1/airports/KJFK/history").json()["data"]
    assert arr["totals"]["ontime_rate"] == 0.5
    assert arr["network"]["ontime_rate"] == 0.75


def test_year_over_year_only_when_prior_period_loaded(client: TestClient) -> None:
    _day("JFK", dt.date(2025, 6, 1), "arrival", 10, 10, 8, 0)
    body = client.get("/api/v1/analytics/overview").json()["data"]
    assert body["previous_year"] is None
    _day("JFK", dt.date(2024, 6, 1), "arrival", 10, 10, 6, 0)
    body = client.get(
        "/api/v1/analytics/overview", params={"start": "2025-06", "end": "2025-06"}
    ).json()["data"]
    assert body["previous_year"]["ontime_rate"] == 0.6


@pytest.mark.parametrize(
    "params", [{"start": "2025-13"}, {"start": "bad"}, {"start": "2025-06", "end": "2025-01"}]
)
def test_invalid_periods_rejected(client: TestClient, params: dict[str, str]) -> None:
    _day("JFK", dt.date(2025, 6, 1), "arrival", 1, 1, 1, 0)
    assert client.get("/api/v1/analytics/overview", params=params).status_code == 422
