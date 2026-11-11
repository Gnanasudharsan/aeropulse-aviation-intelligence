"""SQLAlchemy ORM models (bronze + silver layers). Gold views are created in migrations."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

TZ = DateTime(timezone=True)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# --------------------------------------------------------------------------- reference


class Airport(Base):
    __tablename__ = "airports"

    iata_code: Mapped[str] = mapped_column(String(4), primary_key=True)
    icao_code: Mapped[str] = mapped_column(String(4), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(2))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    elevation_ft: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64))
    airport_type: Mapped[str] = mapped_column(String(32))
    is_monitored: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    reference_source: Mapped[str] = mapped_column(String(64), default="ourairports")
    reference_id: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[dt.datetime] = mapped_column(TZ, server_default=func.now())


# --------------------------------------------------------------------------- bronze / ops


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(String(32), index=True)
    trigger: Mapped[str] = mapped_column(String(16), default="schedule")
    started_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow, index=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    status: Mapped[str] = mapped_column(
        String(16), default="running"
    )  # running|success|partial|failed
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)


class RawPayload(Base):
    """Bronze: upstream payload exactly as received."""

    __tablename__ = "raw_payloads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32))
    ingestion_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL")
    )
    request_url: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    fetched_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow)
    source_published_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    content_type: Mapped[str | None] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    # Null when identical to the previous payload of the same source (dedup storage).
    payload: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_raw_payloads_source_fetched", "source", "fetched_at"),)


class SourceStatus(Base):
    __tablename__ = "source_status"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    source_url: Mapped[str] = mapped_column(Text)
    expected_interval_seconds: Mapped[int] = mapped_column(Integer)
    last_attempt_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    last_success_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    last_failure_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_source_published_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    last_observation_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    last_record_count: Mapped[int | None] = mapped_column(Integer)


class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(32))
    check_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(8))  # pass|warn|fail
    observed_value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow, index=True)


# --------------------------------------------------------------------------- weather (silver)


class WeatherObservation(Base):
    """One METAR/SPECI. Natural key: (station, observed_at, raw text hash)."""

    __tablename__ = "weather_observations"

    station_icao: Mapped[str] = mapped_column(String(4), primary_key=True)
    observed_at: Mapped[dt.datetime] = mapped_column(TZ, primary_key=True)
    raw_hash: Mapped[str] = mapped_column(String(16), primary_key=True)
    airport_iata: Mapped[str] = mapped_column(ForeignKey("airports.iata_code"))
    source_published_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    report_time: Mapped[dt.datetime | None] = mapped_column(TZ)
    ingested_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow)
    metar_type: Mapped[str] = mapped_column(String(8), default="METAR")
    raw_text: Mapped[str] = mapped_column(Text)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    dewpoint_c: Mapped[float | None] = mapped_column(Float)
    wind_dir_deg: Mapped[int | None] = mapped_column(SmallInteger)
    wind_dir_variable: Mapped[bool] = mapped_column(Boolean, default=False)
    wind_speed_kt: Mapped[int | None] = mapped_column(SmallInteger)
    wind_gust_kt: Mapped[int | None] = mapped_column(SmallInteger)
    visibility_sm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    visibility_text: Mapped[str | None] = mapped_column(String(16))
    visibility_is_lower_bound: Mapped[bool] = mapped_column(Boolean, default=False)
    altimeter_hpa: Mapped[float | None] = mapped_column(Float)
    sea_level_pressure_hpa: Mapped[float | None] = mapped_column(Float)
    ceiling_ft: Mapped[int | None] = mapped_column(Integer)
    cloud_layers: Mapped[list[Any]] = mapped_column(default=list)
    wx_string: Mapped[str | None] = mapped_column(String(64))
    flight_category: Mapped[str | None] = mapped_column(String(4))
    flight_category_source: Mapped[str] = mapped_column(String(8), default="awc")

    __table_args__ = (Index("ix_weather_obs_airport_time", "airport_iata", "observed_at"),)


class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    station_icao: Mapped[str] = mapped_column(String(4))
    airport_iata: Mapped[str] = mapped_column(ForeignKey("airports.iata_code"))
    issued_at: Mapped[dt.datetime] = mapped_column(TZ)
    bulletin_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    valid_from: Mapped[dt.datetime] = mapped_column(TZ)
    valid_to: Mapped[dt.datetime] = mapped_column(TZ)
    raw_text: Mapped[str] = mapped_column(Text)
    raw_hash: Mapped[str] = mapped_column(String(16))
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow)

    periods: Mapped[list[WeatherForecastPeriod]] = relationship(
        back_populates="forecast",
        cascade="all, delete-orphan",
        order_by="WeatherForecastPeriod.seq",
    )

    __table_args__ = (
        UniqueConstraint(
            "station_icao", "issued_at", "raw_hash", name="uq_weather_forecasts_natural"
        ),
        Index("ix_weather_fcst_airport_issued", "airport_iata", "issued_at"),
    )


class WeatherForecastPeriod(Base):
    __tablename__ = "weather_forecast_periods"

    forecast_id: Mapped[int] = mapped_column(
        ForeignKey("weather_forecasts.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    time_from: Mapped[dt.datetime] = mapped_column(TZ)
    time_to: Mapped[dt.datetime] = mapped_column(TZ)
    change_indicator: Mapped[str | None] = mapped_column(String(8))
    probability: Mapped[int | None] = mapped_column(SmallInteger)
    wind_dir_deg: Mapped[int | None] = mapped_column(SmallInteger)
    wind_speed_kt: Mapped[int | None] = mapped_column(SmallInteger)
    wind_gust_kt: Mapped[int | None] = mapped_column(SmallInteger)
    visibility_sm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    visibility_text: Mapped[str | None] = mapped_column(String(16))
    wx_string: Mapped[str | None] = mapped_column(String(64))
    ceiling_ft: Mapped[int | None] = mapped_column(Integer)
    cloud_layers: Mapped[list[Any]] = mapped_column(default=list)
    flight_category: Mapped[str | None] = mapped_column(String(4))

    forecast: Mapped[WeatherForecast] = relationship(back_populates="periods")


# --------------------------------------------------------------------------- FAA (silver)


class FaaAdvisory(Base):
    """One FAA NAS Status airport event, tracked across polls (first/last seen, cleared)."""

    __tablename__ = "faa_advisories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(80), unique=True)
    source_event_id: Mapped[str | None] = mapped_column(String(64))
    source_feed: Mapped[str] = mapped_column(String(16))  # faa_json | faa_xml
    airport_code: Mapped[str] = mapped_column(String(8), index=True)  # FAA LID / IATA as published
    airport_iata: Mapped[str | None] = mapped_column(ForeignKey("airports.iata_code"))
    advisory_type: Mapped[str] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(16), default="full")  # full|partial
    reason: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    ends_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    source_updated_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    avg_delay_minutes: Mapped[int | None] = mapped_column(Integer)
    min_delay_minutes: Mapped[int | None] = mapped_column(Integer)
    max_delay_minutes: Mapped[int | None] = mapped_column(Integer)
    trend: Mapped[str | None] = mapped_column(String(16))
    probability_of_extension: Mapped[str | None] = mapped_column(String(16))
    advisory_url: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    content_hash: Mapped[str] = mapped_column(String(16))
    first_seen_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow)
    cleared_at: Mapped[dt.datetime | None] = mapped_column(TZ, index=True)

    __table_args__ = (Index("ix_faa_adv_active", "cleared_at", "advisory_type"),)


class OperationalEvent(Base):
    """Append-only change log: advisory created / updated / cleared, as detected by us."""

    __tablename__ = "operational_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    advisory_id: Mapped[int] = mapped_column(ForeignKey("faa_advisories.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(24))  # created|updated|cleared
    airport_code: Mapped[str] = mapped_column(String(8))
    advisory_type: Mapped[str] = mapped_column(String(32))
    detected_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow)
    source_updated_at: Mapped[dt.datetime | None] = mapped_column(TZ)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL")
    )
    changes: Mapped[dict[str, Any]] = mapped_column(default=dict)

    __table_args__ = (
        Index("ix_op_events_detected", "detected_at"),
        Index("ix_op_events_airport_detected", "airport_code", "detected_at"),
    )


class AirportConfig(Base):
    """Runway configuration / arrival rate snapshots (informational, not advisories)."""

    __tablename__ = "airport_configs"

    airport_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    source_timestamp: Mapped[dt.datetime] = mapped_column(TZ, primary_key=True)
    arrival_runway_config: Mapped[str | None] = mapped_column(String(64))
    departure_runway_config: Mapped[str | None] = mapped_column(String(64))
    arrival_rate: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[dt.datetime] = mapped_column(TZ, default=utcnow)
