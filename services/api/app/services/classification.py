"""Evidence-based classification rules (see analytics/metric_definitions/README.md).

Pure functions — no I/O — so every threshold is unit-testable.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from app.ingestion.sources import SourceSpec

SourceHealth = Literal["healthy", "delayed", "stale", "unavailable"]
AirportStatus = Literal["critical", "warning", "weather", "normal", "unknown"]
WeatherRisk = Literal["low", "elevated", "high", "severe", "unknown"]

OBSERVATION_STALE_AFTER = dt.timedelta(hours=2)


def source_health(
    spec: SourceSpec, reference_time: dt.datetime | None, now: dt.datetime
) -> SourceHealth:
    """Health from the age of the last successful ingestion (or data month end for BTS)."""
    if reference_time is None:
        return "unavailable"
    age = (now - reference_time).total_seconds()
    if age <= spec.healthy_s:
        return "healthy"
    if age <= spec.delayed_s:
        return "delayed"
    if age <= spec.stale_s:
        return "stale"
    return "unavailable"


def observation_is_stale(observed_at: dt.datetime | None, now: dt.datetime) -> bool:
    return observed_at is None or now - observed_at > OBSERVATION_STALE_AFTER


@dataclass(frozen=True, slots=True)
class AirportFlags:
    has_ground_stop: bool = False
    has_ground_delay_program: bool = False
    has_full_closure: bool = False
    has_reported_delay: bool = False
    flight_category: str | None = None
    weather_observed_at: dt.datetime | None = None


@dataclass(frozen=True, slots=True)
class StatusResult:
    status: AirportStatus
    reason: str


def classify_airport(
    flags: AirportFlags, *, now: dt.datetime, faa_health: SourceHealth
) -> StatusResult:
    """Map colour/status. First matching rule wins. Weather never implies an FAA program."""
    if flags.has_ground_stop:
        return StatusResult("critical", "FAA ground stop reported")
    if flags.has_ground_delay_program:
        return StatusResult("critical", "FAA ground delay program reported")
    if flags.has_full_closure:
        return StatusResult("critical", "FAA-reported airport closure in effect")
    if flags.has_reported_delay:
        return StatusResult("warning", "FAA-reported arrival/departure delays")
    weather_fresh = not observation_is_stale(flags.weather_observed_at, now)
    if weather_fresh and flags.flight_category in {"IFR", "LIFR"}:
        return StatusResult(
            "weather", f"{flags.flight_category} conditions observed (no FAA program)"
        )
    if weather_fresh and faa_health in {"healthy", "delayed"}:
        return StatusResult("normal", "No FAA advisories reported; latest METAR current")
    if not weather_fresh:
        return StatusResult("unknown", "No current weather observation")
    return StatusResult("unknown", "FAA status feed is not current")


def weather_risk(
    *,
    flight_category: str | None,
    wind_speed_kt: int | None,
    wind_gust_kt: int | None,
    wx_string: str | None,
    observed_at: dt.datetime | None,
    now: dt.datetime,
) -> tuple[WeatherRisk, list[str]]:
    """Observed-weather risk tier. Describes conditions; it is not a delay forecast."""
    if observation_is_stale(observed_at, now) or flight_category is None:
        return "unknown", ["No current observation"]
    wx = (wx_string or "").upper()
    sustained = wind_speed_kt or 0
    gust = wind_gust_kt or 0
    factors: list[str] = []
    level = 0
    if flight_category == "LIFR":
        level, factors = 3, ["LIFR: ceiling < 500 ft or visibility < 1 SM"]
    if flight_category == "IFR":
        level = max(level, 2)
        factors.append("IFR: ceiling < 1000 ft or visibility < 3 SM")
    if "TS" in wx:
        level = max(level, 2)
        factors.append("Thunderstorm reported")
    if "FZ" in wx:
        level = max(level, 2)
        factors.append("Freezing precipitation/fog reported")
    if gust >= 35:
        level = max(level, 2)
        factors.append(f"Gusts {gust} kt")
    elif gust >= 20 or sustained >= 20:
        level = max(level, 1)
        factors.append(f"Wind {sustained} kt" + (f" gusting {gust} kt" if gust else ""))
    if flight_category == "MVFR":
        level = max(level, 1)
        factors.append("MVFR: ceiling 1000-3000 ft or visibility 3-5 SM")
    tier: WeatherRisk = ("low", "elevated", "high", "severe")[level]
    return tier, factors or ["VFR, light winds"]
