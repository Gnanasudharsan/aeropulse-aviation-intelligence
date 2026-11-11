"""Read-side queries for the API. All SQL is parameterised."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Airport,
    AirportConfig,
    DataQualityResult,
    FaaAdvisory,
    IngestionRun,
    OperationalEvent,
    SourceStatus,
    WeatherForecast,
    WeatherObservation,
)


def airport_status_rows(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(text("SELECT * FROM v_airport_status ORDER BY iata_code")).mappings()
    return [dict(r) for r in rows]


def find_airport(session: Session, code: str) -> Airport | None:
    code = code.upper()
    return session.scalar(
        select(Airport).where(or_(Airport.iata_code == code, Airport.icao_code == code))
    )


def latest_observation(session: Session, iata: str) -> WeatherObservation | None:
    return session.scalar(
        select(WeatherObservation)
        .where(WeatherObservation.airport_iata == iata)
        .order_by(
            WeatherObservation.observed_at.desc(),
            WeatherObservation.source_published_at.desc().nulls_last(),
        )
        .limit(1)
    )


def observations(session: Session, iata: str, since: dt.datetime) -> Sequence[WeatherObservation]:
    return session.scalars(
        select(WeatherObservation)
        .where(WeatherObservation.airport_iata == iata, WeatherObservation.observed_at >= since)
        .order_by(WeatherObservation.observed_at.desc())
    ).all()


def hourly_weather(
    session: Session, iatas: Sequence[str], since: dt.datetime
) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            "SELECT * FROM v_weather_hourly "
            "WHERE airport_iata = ANY(:codes) AND hour_utc >= :since "
            "ORDER BY airport_iata, hour_utc"
        ),
        {"codes": list(iatas), "since": since},
    ).mappings()
    return [dict(r) for r in rows]


def latest_forecast(session: Session, iata: str) -> WeatherForecast | None:
    return session.scalar(
        select(WeatherForecast)
        .options(selectinload(WeatherForecast.periods))
        .where(WeatherForecast.airport_iata == iata)
        .order_by(WeatherForecast.issued_at.desc())
        .limit(1)
    )


def latest_runway_config(session: Session, code: str) -> AirportConfig | None:
    return session.scalar(
        select(AirportConfig)
        .where(AirportConfig.airport_code == code)
        .order_by(AirportConfig.source_timestamp.desc())
        .limit(1)
    )


def _active_clause(now: dt.datetime) -> Any:
    return and_(
        FaaAdvisory.cleared_at.is_(None),
        or_(FaaAdvisory.ends_at.is_(None), FaaAdvisory.ends_at > now),
    )


def advisories_query(
    *,
    now: dt.datetime,
    airport: str | None = None,
    advisory_types: Sequence[str] | None = None,
    state: str = "active",
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
    q: str | None = None,
) -> Select[FaaAdvisory]:
    stmt = select(FaaAdvisory)
    if state == "active":
        stmt = stmt.where(_active_clause(now))
    elif state == "inactive":
        stmt = stmt.where(~_active_clause(now))
    if airport:
        stmt = stmt.where(FaaAdvisory.airport_code == airport.upper())
    if advisory_types:
        stmt = stmt.where(FaaAdvisory.advisory_type.in_(advisory_types))
    if since:
        stmt = stmt.where(FaaAdvisory.last_seen_at >= since)
    if until:
        stmt = stmt.where(FaaAdvisory.first_seen_at <= until)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                FaaAdvisory.airport_code.ilike(like),
                FaaAdvisory.reason.ilike(like),
                FaaAdvisory.text.ilike(like),
            )
        )
    return stmt


def paginate[T](
    session: Session, stmt: Select[T], order_by: Sequence[Any], page: int, page_size: int
) -> tuple[list[T], int]:
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = session.scalars(
        stmt.order_by(*order_by).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return list(rows), int(total)


def events_query(
    *,
    airport: str | None = None,
    advisory_types: Sequence[str] | None = None,
    event_types: Sequence[str] | None = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
) -> Select[OperationalEvent]:
    stmt = select(OperationalEvent)
    if airport:
        stmt = stmt.where(OperationalEvent.airport_code == airport.upper())
    if advisory_types:
        stmt = stmt.where(OperationalEvent.advisory_type.in_(advisory_types))
    if event_types:
        stmt = stmt.where(OperationalEvent.event_type.in_(event_types))
    if since:
        stmt = stmt.where(OperationalEvent.detected_at >= since)
    if until:
        stmt = stmt.where(OperationalEvent.detected_at <= until)
    return stmt


def advisory_timeline(session: Session, advisory_id: int) -> Sequence[OperationalEvent]:
    return session.scalars(
        select(OperationalEvent)
        .where(OperationalEvent.advisory_id == advisory_id)
        .order_by(OperationalEvent.detected_at)
    ).all()


def count_events_since(session: Session, since: dt.datetime) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(OperationalEvent)
            .where(OperationalEvent.detected_at >= since)
        )
        or 0
    )


def recent_events(session: Session, limit: int) -> Sequence[OperationalEvent]:
    return session.scalars(
        select(OperationalEvent)
        .order_by(OperationalEvent.detected_at.desc(), OperationalEvent.id.desc())
        .limit(limit)
    ).all()


def source_rows(session: Session) -> Sequence[SourceStatus]:
    return session.scalars(select(SourceStatus).order_by(SourceStatus.source)).all()


def recent_runs(session: Session, limit: int = 20) -> Sequence[IngestionRun]:
    return session.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    ).all()


def latest_quality(session: Session) -> Sequence[DataQualityResult]:
    """Quality checks from the most recent run of each source."""
    latest_run = (
        select(
            DataQualityResult.source, func.max(DataQualityResult.ingestion_run_id).label("run_id")
        )
        .group_by(DataQualityResult.source)
        .subquery()
    )
    return session.scalars(
        select(DataQualityResult)
        .join(
            latest_run,
            and_(
                DataQualityResult.source == latest_run.c.source,
                DataQualityResult.ingestion_run_id == latest_run.c.run_id,
            ),
        )
        .order_by(DataQualityResult.source, DataQualityResult.check_name)
    ).all()
