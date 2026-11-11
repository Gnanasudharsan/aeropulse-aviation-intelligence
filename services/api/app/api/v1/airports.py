from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app import repositories as repo
from app.api.deps import AirportDep, DbSession, meta, now_utc
from app.models import FaaAdvisory
from app.schemas import (
    AdvisoryOut,
    AirportDetailOut,
    AirportSummaryOut,
    AirportWeatherOut,
    Envelope,
    RunwayConfigOut,
)
from app.services import assemblers as asm
from app.services.classification import weather_risk

router = APIRouter(prefix="/airports", tags=["airports"])

StatusFilter = Literal["critical", "warning", "weather", "normal", "unknown"]


@router.get(
    "",
    response_model=Envelope[list[AirportSummaryOut]],
    summary="Monitored airports with live status",
)
def list_airports(
    db: DbSession,
    response: Response,
    q: Annotated[
        str | None, Query(max_length=64, description="Search code, name, city or state")
    ] = None,
    status: Annotated[list[StatusFilter] | None, Query()] = None,
    flight_category: Annotated[list[Literal["VFR", "MVFR", "IFR", "LIFR"]] | None, Query()] = None,
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
) -> Envelope[list[AirportSummaryOut]]:
    response.headers["Cache-Control"] = "public, max-age=15"
    items = asm.airport_summaries(db, now_utc())
    if q:
        needle = q.lower()
        items = [
            a
            for a in items
            if needle in f"{a.iata_code} {a.icao_code} {a.name} {a.city} {a.state}".lower()
        ]
    if status:
        items = [a for a in items if a.status in status]
    if flight_category:
        items = [a for a in items if a.flight_category in flight_category]
    if state:
        items = [a for a in items if a.state == state.upper()]
    return Envelope(data=items, meta=meta(total=len(items)))


@router.get(
    "/{code}", response_model=Envelope[AirportDetailOut], summary="Airport intelligence detail"
)
def airport_detail(
    airport: AirportDep, db: DbSession, response: Response
) -> Envelope[AirportDetailOut]:
    response.headers["Cache-Control"] = "public, max-age=15"
    now = now_utc()
    summary = next(s for s in asm.airport_summaries(db, now) if s.iata_code == airport.iata_code)
    obs = repo.latest_observation(db, airport.iata_code)
    _, factors = weather_risk(
        flight_category=obs.flight_category if obs else None,
        wind_speed_kt=obs.wind_speed_kt if obs else None,
        wind_gust_kt=obs.wind_gust_kt if obs else None,
        wx_string=obs.wx_string if obs else None,
        observed_at=obs.observed_at if obs else None,
        now=now,
    )
    advisories = db.scalars(
        repo.advisories_query(now=now, airport=airport.iata_code, state="active").order_by(
            FaaAdvisory.first_seen_at.desc()
        )
    ).all()
    cfg = repo.latest_runway_config(db, airport.iata_code)
    detail = AirportDetailOut(
        **summary.model_dump(),
        elevation_ft=airport.elevation_ft,
        weather_risk_factors=factors,
        latest_weather=asm.observation_out(obs, now) if obs else None,
        active_advisory_list=[asm.advisory_out(a, now) for a in advisories],
        forecast=asm.forecast_out(repo.latest_forecast(db, airport.iata_code)),
        runway_config=RunwayConfigOut.model_validate(cfg) if cfg else None,
    )
    return Envelope(data=detail, meta=meta())


@router.get(
    "/{code}/weather",
    response_model=Envelope[AirportWeatherOut],
    summary="Observation history + TAF",
)
def airport_weather(
    airport: AirportDep,
    db: DbSession,
    response: Response,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> Envelope[AirportWeatherOut]:
    response.headers["Cache-Control"] = "public, max-age=30"
    now = now_utc()
    since = now - dt.timedelta(hours=hours)
    return Envelope(
        data=AirportWeatherOut(
            airport=airport.iata_code,
            observations=[
                asm.observation_out(o, now) for o in repo.observations(db, airport.iata_code, since)
            ],
            hourly=[asm.hour_out(r) for r in repo.hourly_weather(db, [airport.iata_code], since)],
            forecast=asm.forecast_out(repo.latest_forecast(db, airport.iata_code)),
        ),
        meta=meta(),
    )


@router.get(
    "/{code}/advisories", response_model=Envelope[list[AdvisoryOut]], summary="FAA advisories"
)
def airport_advisories(
    airport: AirportDep,
    db: DbSession,
    response: Response,
    state: Annotated[Literal["active", "inactive", "all"], Query()] = "all",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Envelope[list[AdvisoryOut]]:
    response.headers["Cache-Control"] = "public, max-age=15"
    now = now_utc()
    rows = db.scalars(
        repo.advisories_query(now=now, airport=airport.iata_code, state=state)
        .order_by(FaaAdvisory.last_seen_at.desc())
        .limit(limit)
    ).all()
    return Envelope(data=[asm.advisory_out(a, now) for a in rows], meta=meta(total=len(rows)))
