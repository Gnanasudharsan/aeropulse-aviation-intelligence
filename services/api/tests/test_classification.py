from __future__ import annotations

import datetime as dt

import pytest

from app.ingestion.sources import SOURCES
from app.services.classification import AirportFlags, classify_airport, source_health, weather_risk

NOW = dt.datetime(2026, 11, 11, 12, 0, tzinfo=dt.UTC)
FRESH = NOW - dt.timedelta(minutes=30)
STALE = NOW - dt.timedelta(hours=3)


@pytest.mark.parametrize(
    ("age_min", "expected"),
    [
        (None, "unavailable"),
        (5, "healthy"),
        (10, "healthy"),
        (11, "delayed"),
        (30, "delayed"),
        (31, "stale"),
        (6 * 60, "stale"),
        (6 * 60 + 1, "unavailable"),
    ],
)
def test_faa_source_health_thresholds(age_min: int | None, expected: str) -> None:
    ref = None if age_min is None else NOW - dt.timedelta(minutes=age_min)
    assert source_health(SOURCES["faa_nas_status"], ref, NOW) == expected


def test_delayed_ingestion_is_reported_as_delayed_for_metar() -> None:
    assert source_health(SOURCES["awc_metar"], NOW - dt.timedelta(minutes=45), NOW) == "delayed"


@pytest.mark.parametrize(
    ("flags", "faa", "status"),
    [
        (AirportFlags(has_ground_stop=True, has_reported_delay=True), "healthy", "critical"),
        (AirportFlags(has_ground_delay_program=True), "healthy", "critical"),
        (AirportFlags(has_full_closure=True), "healthy", "critical"),
        (
            AirportFlags(has_reported_delay=True, flight_category="IFR", weather_observed_at=FRESH),
            "healthy",
            "warning",
        ),
        (AirportFlags(flight_category="LIFR", weather_observed_at=FRESH), "healthy", "weather"),
        (AirportFlags(flight_category="VFR", weather_observed_at=FRESH), "healthy", "normal"),
        (AirportFlags(flight_category="VFR", weather_observed_at=FRESH), "delayed", "normal"),
        # FAA feed not current -> cannot claim "normal"
        (AirportFlags(flight_category="VFR", weather_observed_at=FRESH), "stale", "unknown"),
        # stale weather: IFR no longer asserted, status unknown
        (AirportFlags(flight_category="IFR", weather_observed_at=STALE), "healthy", "unknown"),
        (AirportFlags(), "healthy", "unknown"),
    ],
)
def test_airport_status_rules(flags: AirportFlags, faa: str, status: str) -> None:
    assert classify_airport(flags, now=NOW, faa_health=faa).status == status  # type: ignore[arg-type]


def test_poor_weather_never_becomes_ground_stop() -> None:
    res = classify_airport(
        AirportFlags(flight_category="LIFR", weather_observed_at=FRESH),
        now=NOW,
        faa_health="healthy",
    )
    assert res.status == "weather" and "no FAA program" in res.reason


@pytest.mark.parametrize(
    ("cat", "wspd", "wgst", "wx", "tier"),
    [
        ("VFR", 5, None, None, "low"),
        ("VFR", 22, None, None, "elevated"),
        ("MVFR", 5, None, None, "elevated"),
        ("VFR", 15, 38, None, "high"),
        ("VFR", 10, None, "TSRA", "high"),
        ("VFR", 10, None, "FZFG", "high"),
        ("IFR", 5, None, None, "high"),
        ("LIFR", 5, None, None, "severe"),
    ],
)
def test_weather_risk_tiers(
    cat: str, wspd: int, wgst: int | None, wx: str | None, tier: str
) -> None:
    got, factors = weather_risk(
        flight_category=cat,
        wind_speed_kt=wspd,
        wind_gust_kt=wgst,
        wx_string=wx,
        observed_at=FRESH,
        now=NOW,
    )
    assert got == tier and factors


def test_weather_risk_unknown_when_observation_stale() -> None:
    got, _ = weather_risk(
        flight_category="LIFR",
        wind_speed_kt=0,
        wind_gust_kt=None,
        wx_string=None,
        observed_at=STALE,
        now=NOW,
    )
    assert got == "unknown"
