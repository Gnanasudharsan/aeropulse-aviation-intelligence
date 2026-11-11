"""API response contracts. The web app mirrors these with Zod (apps/web/lib/api/schemas.ts)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.classification import AirportStatus, SourceHealth, WeatherRisk


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Meta(Model):
    generated_at: dt.datetime
    page: int | None = None
    page_size: int | None = None
    total: int | None = None
    total_pages: int | None = None


class Envelope[T](Model):
    data: T
    meta: Meta


class ErrorBody(Model):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(Model):
    error: ErrorBody


# --------------------------------------------------------------------------- health / freshness


class HealthOut(Model):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "unavailable"]
    time: dt.datetime


class SourceFreshness(Model):
    source: str
    display_name: str
    source_url: str
    health: SourceHealth
    expected_interval_seconds: int
    last_attempt_at: dt.datetime | None
    last_success_at: dt.datetime | None
    last_failure_at: dt.datetime | None
    last_error: str | None
    consecutive_failures: int
    last_source_published_at: dt.datetime | None
    last_observation_at: dt.datetime | None
    last_record_count: int | None
    age_seconds: float | None
    thresholds_seconds: dict[str, int]
    limitations: str


class IngestionRunOut(Model):
    id: int
    job: str
    trigger: str
    status: str
    started_at: dt.datetime
    finished_at: dt.datetime | None
    records_fetched: int
    records_inserted: int
    records_updated: int
    records_rejected: int
    error_message: str | None


class QualityCheckOut(Model):
    source: str
    check_name: str
    status: str
    observed_value: float | None
    threshold: str | None
    message: str | None
    checked_at: dt.datetime


class SystemStatusOut(Model):
    overall: SourceHealth
    sources: list[SourceFreshness]
    recent_runs: list[IngestionRunOut]
    latest_quality: list[QualityCheckOut]


# --------------------------------------------------------------------------- weather


class CloudLayer(Model):
    cover: str | None
    base_ft: int | None


class WeatherObservationOut(Model):
    station_icao: str
    observed_at: dt.datetime
    source_published_at: dt.datetime | None
    ingested_at: dt.datetime
    metar_type: str
    raw_text: str
    temperature_c: float | None
    dewpoint_c: float | None
    wind_dir_deg: int | None
    wind_dir_variable: bool
    wind_speed_kt: int | None
    wind_gust_kt: int | None
    visibility_sm: float | None
    visibility_text: str | None
    visibility_is_lower_bound: bool
    altimeter_hpa: float | None
    ceiling_ft: int | None
    cloud_layers: list[CloudLayer]
    wx_string: str | None
    flight_category: str | None
    flight_category_source: str
    is_stale: bool


class ForecastPeriodOut(Model):
    seq: int
    time_from: dt.datetime
    time_to: dt.datetime
    change_indicator: str | None
    probability: int | None
    wind_dir_deg: int | None
    wind_speed_kt: int | None
    wind_gust_kt: int | None
    visibility_sm: float | None
    visibility_text: str | None
    wx_string: str | None
    ceiling_ft: int | None
    flight_category: str | None


class ForecastOut(Model):
    station_icao: str
    issued_at: dt.datetime
    valid_from: dt.datetime
    valid_to: dt.datetime
    raw_text: str
    is_amendment: bool
    ingested_at: dt.datetime
    periods: list[ForecastPeriodOut]


class WeatherHourOut(Model):
    hour_utc: dt.datetime
    observations: int
    avg_temperature_c: float | None
    max_wind_speed_kt: int | None
    max_wind_gust_kt: int | None
    min_visibility_sm: float | None
    min_ceiling_ft: int | None
    worst_flight_category: str | None


class AirportWeatherOut(Model):
    airport: str
    observations: list[WeatherObservationOut]
    hourly: list[WeatherHourOut]
    forecast: ForecastOut | None


# --------------------------------------------------------------------------- advisories / events


class AdvisoryOut(Model):
    id: int
    event_key: str
    airport_code: str
    airport_iata: str | None
    advisory_type: str
    scope: str
    reason: str | None
    text: str | None
    starts_at: dt.datetime | None
    ends_at: dt.datetime | None
    source_updated_at: dt.datetime | None
    avg_delay_minutes: int | None
    min_delay_minutes: int | None
    max_delay_minutes: int | None
    trend: str | None
    probability_of_extension: str | None
    advisory_url: str | None
    details: dict[str, Any]
    source_feed: str
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime
    cleared_at: dt.datetime | None
    is_active: bool


class OperationalEventOut(Model):
    id: int
    advisory_id: int
    event_type: str
    airport_code: str
    advisory_type: str
    detected_at: dt.datetime
    source_updated_at: dt.datetime | None
    changes: dict[str, Any]


class AdvisoryDetailOut(AdvisoryOut):
    timeline: list[OperationalEventOut]
    source_url: str = "https://nasstatus.faa.gov/"


# --------------------------------------------------------------------------- airports


class AirportSummaryOut(Model):
    iata_code: str
    icao_code: str
    name: str
    city: str
    state: str
    latitude: float
    longitude: float
    timezone: str
    status: AirportStatus
    status_reason: str
    weather_risk: WeatherRisk
    weather_observed_at: dt.datetime | None
    weather_is_stale: bool
    flight_category: str | None
    visibility_sm: float | None
    ceiling_ft: int | None
    wind_speed_kt: int | None
    wind_gust_kt: int | None
    temperature_c: float | None
    wx_string: str | None
    active_advisories: int
    has_ground_stop: bool
    has_ground_delay_program: bool
    has_full_closure: bool
    has_reported_delay: bool
    has_partial_closure: bool


class RunwayConfigOut(Model):
    source_timestamp: dt.datetime
    arrival_runway_config: str | None
    departure_runway_config: str | None
    arrival_rate: int | None


class AirportDetailOut(AirportSummaryOut):
    elevation_ft: int | None
    weather_risk_factors: list[str]
    latest_weather: WeatherObservationOut | None
    active_advisory_list: list[AdvisoryOut]
    forecast: ForecastOut | None
    runway_config: RunwayConfigOut | None


# ------------------------------------------------------------------ operations / weather overview


class CategoryCount(Model):
    category: str
    airports: int


class OperationsSummaryOut(Model):
    monitored_airports: int
    airports_with_active_advisories: int
    airports_with_disruptions: int
    active_ground_stops: int
    active_ground_delay_programs: int
    active_full_closures: int
    active_reported_delays: int
    active_partial_closures: int
    status_counts: dict[str, int]
    flight_categories: list[CategoryCount]
    changes_last_hour: int
    recent_changes: list[OperationalEventOut]
    faa_health: SourceHealth
    weather_health: SourceHealth
    faa_last_success_at: dt.datetime | None
    weather_last_success_at: dt.datetime | None
    latest_observation_at: dt.datetime | None


class WeatherExtreme(Model):
    airport: str
    value: float
    observed_at: dt.datetime


class WeatherOverviewOut(Model):
    airports: list[AirportSummaryOut]
    flight_categories: list[CategoryCount]
    risk_counts: dict[str, int]
    lowest_visibility: list[WeatherExtreme]
    strongest_wind: list[WeatherExtreme]
    lowest_ceiling: list[WeatherExtreme]
    weather_health: SourceHealth
    advisory_weather_overlap: list[str] = Field(
        description="Airports with an active FAA advisory whose latest METAR is IFR/LIFR. "
        "Co-occurrence only; not a causal claim."
    )


class WeatherTrendSeries(Model):
    airport: str
    hourly: list[WeatherHourOut]
