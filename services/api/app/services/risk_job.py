"""Compute and persist risk scores for all monitored airports."""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, selectinload

from app import repositories as repo
from app.models import Airport, WeatherForecast
from app.services import assemblers as asm
from app.services import risk
from app.services.classification import weather_risk
from app.services.risk_model import load_model


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, dt.datetime) else None


def historical_rates(
    session: Session, keys: list[tuple[str, int, int]]
) -> dict[str, tuple[float, int]]:
    """(airport, calendar month, local hour) -> departures delayed>=15 or cancelled / scheduled."""
    if not keys:
        return {}
    rows = session.execute(
        text(
            """
            WITH k(airport, mon, hr) AS (SELECT * FROM unnest(CAST(:airports AS text[]), CAST(:months AS int[]), CAST(:hours AS int[])))
            SELECT h.airport_iata, sum(h.delayed_15 + h.cancelled)::float / nullif(sum(h.flights), 0),
                   sum(h.flights)::int
            FROM airport_performance_hourly h
            JOIN k ON k.airport = h.airport_iata AND k.mon = extract(month FROM h.year_month)
                  AND k.hr = h.hour_local
            WHERE h.direction = 'departure'
            GROUP BY h.airport_iata
            """
        ),
        {
            "airports": [k[0] for k in keys],
            "months": [k[1] for k in keys],
            "hours": [k[2] for k in keys],
        },
    ).all()
    return {r[0]: (float(r[1]), int(r[2])) for r in rows if r[1] is not None and r[2] >= 30}


def compute_all(session: Session, now: dt.datetime) -> list[dict[str, Any]]:
    fresh = asm.all_freshness(session, now)
    faa_current = fresh["faa_nas_status"].health in {"healthy", "delayed"}
    status_rows = {r["iata_code"]: r for r in repo.airport_status_rows(session)}
    airports = list(session.scalars(select(Airport).where(Airport.is_monitored)))
    local = {a.iata_code: now.astimezone(ZoneInfo(a.timezone)) for a in airports}
    hist = historical_rates(session, [(c, t.month, t.hour) for c, t in local.items()])

    latest_fc: dict[str, WeatherForecast] = {}
    for forecast in session.scalars(
        select(WeatherForecast)
        .options(selectinload(WeatherForecast.periods))
        .where(WeatherForecast.valid_to > now)
        .order_by(WeatherForecast.airport_iata, WeatherForecast.issued_at.desc())
    ):
        latest_fc.setdefault(forecast.airport_iata, forecast)

    model = load_model()
    out = []
    for a in airports:
        row = status_rows.get(a.iata_code, {})
        obs_risk, _ = weather_risk(
            flight_category=row.get("flight_category"),
            wind_speed_kt=row.get("wind_speed_kt"),
            wind_gust_kt=row.get("wind_gust_kt"),
            wx_string=row.get("wx_string"),
            observed_at=row.get("weather_observed_at"),
            now=now,
        )
        fc = latest_fc.get(a.iata_code)
        periods = tuple(
            risk.ForecastPeriodInput(
                p.time_from,
                p.time_to,
                p.flight_category,
                p.wx_string,
                p.wind_gust_kt,
                p.change_indicator,
            )
            for p in (fc.periods if fc else [])
        )
        h = hist.get(a.iata_code)
        inputs = risk.RiskInputs(
            has_ground_stop=bool(row.get("has_ground_stop")),
            has_ground_delay_program=bool(row.get("has_ground_delay_program")),
            has_full_closure=bool(row.get("has_full_closure")),
            has_reported_delay=bool(row.get("has_reported_delay")),
            faa_current=faa_current,
            observed_risk=obs_risk,
            forecast_periods=periods,
            historical_disruption_rate=h[0] if h else None,
            historical_flights=h[1] if h else None,
        )
        result = risk.score(inputs, now)
        model_out = model.predict(row, local[a.iata_code], a.iata_code, now) if model else None
        out.append(
            {
                "airport_iata": a.iata_code,
                "computed_at": now,
                "method_version": result.method_version,
                "score": result.score,
                "category": result.category,
                "components": [dataclasses.asdict(c) for c in result.components],
                "missing_inputs": result.missing_inputs,
                "model_version": model.version if model and model_out else None,
                "model_probability": model_out.probability if model_out else None,
                "model_contributions": model_out.contributions if model_out else None,
                "inputs_as_of": {
                    "metar_observed_at": _iso(row.get("weather_observed_at")),
                    "taf_issued_at": fc.issued_at.isoformat() if fc else None,
                    "faa_last_success_at": _iso(fresh["faa_nas_status"].last_success_at),
                    "local_time": local[a.iata_code].isoformat(),
                },
            }
        )
    return out


def persist(session: Session, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    stmt = text(
        """INSERT INTO risk_scores (airport_iata, computed_at, method_version, score, category, components,
               missing_inputs, model_version, model_probability, model_contributions, inputs_as_of)
           VALUES (:airport_iata, :computed_at, :method_version, :score, :category, :components,
               :missing_inputs, :model_version, :model_probability, :model_contributions, :inputs_as_of)"""
    ).bindparams(
        bindparam("components", type_=JSONB),
        bindparam("missing_inputs", type_=JSONB),
        bindparam("model_contributions", type_=JSONB),
        bindparam("inputs_as_of", type_=JSONB),
    )
    session.execute(stmt, rows)
    return len(rows)
