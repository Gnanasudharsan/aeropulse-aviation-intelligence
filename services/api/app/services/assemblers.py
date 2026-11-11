"""Turn query results into API schemas, applying the classification rules."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from app import repositories as repo
from app.ingestion.sources import SOURCES
from app.models import (
    FaaAdvisory,
    OperationalEvent,
    SourceStatus,
    WeatherForecast,
    WeatherObservation,
)
from app.schemas import (
    AdvisoryOut,
    AirportSummaryOut,
    ForecastOut,
    ForecastPeriodOut,
    OperationalEventOut,
    SourceFreshness,
    WeatherHourOut,
    WeatherObservationOut,
)
from app.services.classification import (
    AirportFlags,
    SourceHealth,
    classify_airport,
    observation_is_stale,
    source_health,
    weather_risk,
)


def freshness(row: SourceStatus | None, key: str, now: dt.datetime) -> SourceFreshness:
    spec = SOURCES[key]
    # BTS freshness is measured from the end of the latest data month (last_observation_at).
    ref = (row.last_observation_at if key == "bts_ontime" else row.last_success_at) if row else None
    return SourceFreshness(
        source=key,
        display_name=spec.display_name,
        source_url=spec.url,
        health=source_health(spec, ref, now),
        expected_interval_seconds=spec.expected_interval_s,
        last_attempt_at=row.last_attempt_at if row else None,
        last_success_at=row.last_success_at if row else None,
        last_failure_at=row.last_failure_at if row else None,
        last_error=row.last_error if row else None,
        consecutive_failures=row.consecutive_failures if row else 0,
        last_source_published_at=row.last_source_published_at if row else None,
        last_observation_at=row.last_observation_at if row else None,
        last_record_count=row.last_record_count if row else None,
        age_seconds=(now - ref).total_seconds() if ref else None,
        thresholds_seconds={
            "healthy": spec.healthy_s,
            "delayed": spec.delayed_s,
            "stale": spec.stale_s,
        },
        limitations=spec.limitations,
    )


def all_freshness(session: Session, now: dt.datetime) -> dict[str, SourceFreshness]:
    rows = {r.source: r for r in repo.source_rows(session)}
    return {key: freshness(rows.get(key), key, now) for key in SOURCES}


def airport_summary(
    row: dict[str, Any], *, now: dt.datetime, faa_health: SourceHealth
) -> AirportSummaryOut:
    flags = AirportFlags(
        has_ground_stop=row["has_ground_stop"],
        has_ground_delay_program=row["has_ground_delay_program"],
        has_full_closure=row["has_full_closure"],
        has_reported_delay=row["has_reported_delay"],
        flight_category=row["flight_category"],
        weather_observed_at=row["weather_observed_at"],
    )
    status = classify_airport(flags, now=now, faa_health=faa_health)
    risk, _ = weather_risk(
        flight_category=row["flight_category"],
        wind_speed_kt=row["wind_speed_kt"],
        wind_gust_kt=row["wind_gust_kt"],
        wx_string=row["wx_string"],
        observed_at=row["weather_observed_at"],
        now=now,
    )
    vis = row["visibility_sm"]
    return AirportSummaryOut(
        iata_code=row["iata_code"],
        icao_code=row["icao_code"],
        name=row["name"],
        city=row["city"],
        state=row["state"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        timezone=row["timezone"],
        status=status.status,
        status_reason=status.reason,
        weather_risk=risk,
        weather_observed_at=row["weather_observed_at"],
        weather_is_stale=observation_is_stale(row["weather_observed_at"], now),
        flight_category=row["flight_category"],
        visibility_sm=float(vis) if vis is not None else None,
        ceiling_ft=row["ceiling_ft"],
        wind_speed_kt=row["wind_speed_kt"],
        wind_gust_kt=row["wind_gust_kt"],
        temperature_c=row["temperature_c"],
        wx_string=row["wx_string"],
        active_advisories=row["active_advisories"],
        has_ground_stop=row["has_ground_stop"],
        has_ground_delay_program=row["has_ground_delay_program"],
        has_full_closure=row["has_full_closure"],
        has_reported_delay=row["has_reported_delay"],
        has_partial_closure=row["has_partial_closure"],
    )


def airport_summaries(session: Session, now: dt.datetime) -> list[AirportSummaryOut]:
    faa = all_freshness(session, now)["faa_nas_status"].health
    return [airport_summary(r, now=now, faa_health=faa) for r in repo.airport_status_rows(session)]


def observation_out(obs: WeatherObservation, now: dt.datetime) -> WeatherObservationOut:
    return WeatherObservationOut.model_validate(
        {
            **{c: getattr(obs, c) for c in WeatherObservationOut.model_fields if hasattr(obs, c)},
            "visibility_sm": float(obs.visibility_sm) if obs.visibility_sm is not None else None,
            "cloud_layers": obs.cloud_layers or [],
            "is_stale": observation_is_stale(obs.observed_at, now),
        }
    )


def forecast_out(fc: WeatherForecast | None) -> ForecastOut | None:
    if fc is None:
        return None
    return ForecastOut(
        station_icao=fc.station_icao,
        issued_at=fc.issued_at,
        valid_from=fc.valid_from,
        valid_to=fc.valid_to,
        raw_text=fc.raw_text,
        is_amendment=fc.is_amendment,
        ingested_at=fc.ingested_at,
        periods=[
            ForecastPeriodOut.model_validate(
                {
                    **{c: getattr(p, c) for c in ForecastPeriodOut.model_fields},
                    "visibility_sm": float(p.visibility_sm)
                    if p.visibility_sm is not None
                    else None,
                }
            )
            for p in fc.periods
        ],
    )


def hour_out(row: dict[str, Any]) -> WeatherHourOut:
    return WeatherHourOut(
        hour_utc=row["hour_utc"],
        observations=row["observations"],
        avg_temperature_c=round(row["avg_temperature_c"], 1)
        if row["avg_temperature_c"] is not None
        else None,
        max_wind_speed_kt=row["max_wind_speed_kt"],
        max_wind_gust_kt=row["max_wind_gust_kt"],
        min_visibility_sm=float(row["min_visibility_sm"])
        if row["min_visibility_sm"] is not None
        else None,
        min_ceiling_ft=row["min_ceiling_ft"],
        worst_flight_category=row["worst_flight_category"],
    )


def advisory_out(a: FaaAdvisory, now: dt.datetime) -> AdvisoryOut:
    active = a.cleared_at is None and (a.ends_at is None or a.ends_at > now)
    return AdvisoryOut.model_validate(
        {
            **{c: getattr(a, c) for c in AdvisoryOut.model_fields if c != "is_active"},
            "is_active": active,
        }
    )


def event_out(e: OperationalEvent) -> OperationalEventOut:
    return OperationalEventOut.model_validate(e)
