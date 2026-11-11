"""Disruption Risk Indicator — transparent, rules-based baseline (``rules-v1``).

The indicator summarises *conditions associated with disruption* at an airport. It is not a
prediction that any specific flight will be delayed or cancelled. Every point added is
returned as a named, explained component.

Components (points, capped at 100):

1. FAA reported state       — ground stop / GDP / full closure: 45; reported delays: 25
2. Observed weather (METAR) — severe 25, high 18, elevated 8, low 0
3. Forecast (TAF, next 6 h) — worst period LIFR 15 / IFR 10; thunderstorm +10;
                              gusts >= 35 kt +8 (>= 25 kt +4); component capped at 20
4. Historical baseline (BTS)— departures delayed >= 15 min or cancelled at this airport,
                              in this calendar month and scheduled local hour:
                              clamp((rate - 0.15) * 60, 0, 15)

Categories: low < 20 <= moderate < 40 <= elevated < 60 <= high.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

METHOD_VERSION = "rules-v1"
FORECAST_HORIZON = dt.timedelta(hours=6)
RiskCategory = Literal["low", "moderate", "elevated", "high"]


@dataclass(frozen=True, slots=True)
class ForecastPeriodInput:
    time_from: dt.datetime
    time_to: dt.datetime
    flight_category: str | None
    wx_string: str | None
    wind_gust_kt: int | None
    change_indicator: str | None


@dataclass(frozen=True, slots=True)
class RiskInputs:
    has_ground_stop: bool = False
    has_ground_delay_program: bool = False
    has_full_closure: bool = False
    has_reported_delay: bool = False
    faa_current: bool = True
    observed_risk: str = "unknown"  # low|elevated|high|severe|unknown (classification.weather_risk)
    forecast_periods: tuple[ForecastPeriodInput, ...] = ()
    historical_disruption_rate: float | None = None  # BTS month x local hour
    historical_flights: int | None = None


@dataclass(slots=True)
class Component:
    key: str
    label: str
    points: float
    max_points: float
    detail: str
    source: str


@dataclass(slots=True)
class RiskResult:
    score: float
    category: RiskCategory
    components: list[Component] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    method_version: str = METHOD_VERSION


def category_for(score: float) -> RiskCategory:
    if score >= 60:
        return "high"
    if score >= 40:
        return "elevated"
    if score >= 20:
        return "moderate"
    return "low"


def _faa(i: RiskInputs) -> Component:
    if i.has_ground_stop or i.has_ground_delay_program or i.has_full_closure:
        what = ", ".join(
            n
            for n, f in (
                ("ground stop", i.has_ground_stop),
                ("ground delay program", i.has_ground_delay_program),
                ("full closure", i.has_full_closure),
            )
            if f
        )
        return Component(
            "faa", "FAA reported state", 45, 45, f"Active FAA {what}", "FAA NAS Status"
        )
    if i.has_reported_delay:
        return Component(
            "faa",
            "FAA reported state",
            25,
            45,
            "FAA-reported arrival/departure delays",
            "FAA NAS Status",
        )
    return Component(
        "faa", "FAA reported state", 0, 45, "No FAA program or delay reported", "FAA NAS Status"
    )


_OBS_POINTS = {"severe": 25.0, "high": 18.0, "elevated": 8.0, "low": 0.0}


def _observed(i: RiskInputs) -> Component:
    pts = _OBS_POINTS.get(i.observed_risk, 0.0)
    detail = (
        f"Observed weather risk: {i.observed_risk}"
        if i.observed_risk != "unknown"
        else "No current METAR"
    )
    return Component("observed", "Observed weather (METAR)", pts, 25, detail, "NOAA AWC METAR")


def _forecast(i: RiskInputs, now: dt.datetime) -> Component:
    horizon = now + FORECAST_HORIZON
    window = [p for p in i.forecast_periods if p.time_from < horizon and p.time_to > now]
    if not window:
        return Component(
            "forecast",
            "Forecast (TAF, next 6 h)",
            0,
            20,
            "No TAF period covers the next 6 hours",
            "NOAA AWC TAF",
        )
    cats = {p.flight_category for p in window}
    pts, notes = 0.0, []
    if "LIFR" in cats:
        pts, notes = 15, ["LIFR forecast"]
    elif "IFR" in cats:
        pts, notes = 10, ["IFR forecast"]
    if any("TS" in (p.wx_string or "") for p in window):
        pts += 10
        notes.append("thunderstorms forecast")
    gust = max((p.wind_gust_kt or 0) for p in window)
    if gust >= 35:
        pts += 8
        notes.append(f"gusts {gust} kt")
    elif gust >= 25:
        pts += 4
        notes.append(f"gusts {gust} kt")
    pts = min(pts, 20)
    return Component(
        "forecast",
        "Forecast (TAF, next 6 h)",
        pts,
        20,
        "; ".join(notes) if notes else "VFR/MVFR forecast, no significant weather",
        "NOAA AWC TAF",
    )


def _historical(i: RiskInputs) -> Component:
    if i.historical_disruption_rate is None:
        return Component(
            "historical",
            "Historical baseline (BTS)",
            0,
            15,
            "No historical data for this airport/month/hour",
            "BTS On-Time Performance",
        )
    rate = i.historical_disruption_rate
    pts = round(max(0.0, min(15.0, (rate - 0.15) * 60)), 1)
    flights = f" across {i.historical_flights:,} departures" if i.historical_flights else ""
    return Component(
        "historical",
        "Historical baseline (BTS)",
        pts,
        15,
        f"{rate:.0%} of departures delayed ≥15 min or cancelled in this month and hour{flights}",
        "BTS On-Time Performance",
    )


def score(i: RiskInputs, now: dt.datetime) -> RiskResult:
    comps = [_faa(i), _observed(i), _forecast(i, now), _historical(i)]
    missing = []
    if not i.faa_current:
        missing.append("faa")
    if i.observed_risk == "unknown":
        missing.append("observed")
    if not i.forecast_periods:
        missing.append("forecast")
    if i.historical_disruption_rate is None:
        missing.append("historical")
    total = min(100.0, round(sum(c.points for c in comps), 1))
    return RiskResult(
        score=total, category=category_for(total), components=comps, missing_inputs=missing
    )
