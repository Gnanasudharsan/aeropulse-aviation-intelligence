from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from app import repositories as repo
from app.api.deps import DbSession, meta, now_utc
from app.schemas import (
    CategoryCount,
    Envelope,
    WeatherExtreme,
    WeatherOverviewOut,
    WeatherTrendSeries,
)
from app.services import assemblers as asm

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get(
    "/overview",
    response_model=Envelope[WeatherOverviewOut],
    summary="National observed-weather picture",
)
def overview(db: DbSession, response: Response) -> Envelope[WeatherOverviewOut]:
    response.headers["Cache-Control"] = "public, max-age=30"
    now = now_utc()
    airports = asm.airport_summaries(db, now)
    current = [a for a in airports if not a.weather_is_stale and a.weather_observed_at]
    cats = Counter(a.flight_category for a in current if a.flight_category)
    risks = Counter(a.weather_risk for a in airports)

    def top(values: list[tuple[str, float, dt.datetime]], reverse: bool) -> list[WeatherExtreme]:
        ranked = sorted(values, key=lambda v: v[1], reverse=reverse)[:5]
        return [WeatherExtreme(airport=c, value=v, observed_at=t) for c, v, t in ranked]

    data = WeatherOverviewOut(
        airports=airports,
        flight_categories=[
            CategoryCount(category=c, airports=cats.get(c, 0))
            for c in ("VFR", "MVFR", "IFR", "LIFR")
        ],
        risk_counts={r: risks.get(r, 0) for r in ("low", "elevated", "high", "severe", "unknown")},
        lowest_visibility=top(
            [
                (a.iata_code, a.visibility_sm, a.weather_observed_at)
                for a in current
                if a.visibility_sm is not None and a.weather_observed_at
            ],
            reverse=False,
        ),
        strongest_wind=top(
            [
                (
                    a.iata_code,
                    float(max(a.wind_speed_kt or 0, a.wind_gust_kt or 0)),
                    a.weather_observed_at,
                )
                for a in current
                if a.weather_observed_at
            ],
            reverse=True,
        ),
        lowest_ceiling=top(
            [
                (a.iata_code, float(a.ceiling_ft), a.weather_observed_at)
                for a in current
                if a.ceiling_ft is not None and a.weather_observed_at
            ],
            reverse=False,
        ),
        weather_health=asm.all_freshness(db, now)["awc_metar"].health,
        advisory_weather_overlap=[
            a.iata_code
            for a in current
            if a.active_advisories > 0 and a.flight_category in {"IFR", "LIFR"}
        ],
    )
    return Envelope(data=data, meta=meta())


@router.get(
    "/trends",
    response_model=Envelope[list[WeatherTrendSeries]],
    summary="Hourly trends for airports",
)
def trends(
    db: DbSession,
    response: Response,
    airports: Annotated[
        str, Query(description="Comma-separated IATA codes (max 8)", max_length=40)
    ],
    hours: Annotated[int, Query(ge=1, le=168)] = 48,
) -> Envelope[list[WeatherTrendSeries]]:
    response.headers["Cache-Control"] = "public, max-age=60"
    codes = [c.strip().upper() for c in airports.split(",") if c.strip()]
    if not codes or len(codes) > 8 or any(len(c) != 3 or not c.isalnum() for c in codes):
        raise HTTPException(status_code=422, detail="Provide 1-8 comma-separated IATA codes")
    known = {a.iata_code for a in asm.airport_summaries(db, now_utc())}
    unknown = [c for c in codes if c not in known]
    if unknown:
        raise HTTPException(status_code=404, detail=f"Airports not monitored: {', '.join(unknown)}")
    rows = repo.hourly_weather(db, codes, now_utc() - dt.timedelta(hours=hours))
    series = [
        WeatherTrendSeries(
            airport=c, hourly=[asm.hour_out(r) for r in rows if r["airport_iata"] == c]
        )
        for c in codes
    ]
    return Envelope(data=series, meta=meta())
