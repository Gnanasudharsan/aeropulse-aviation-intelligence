/**
 * Runtime contracts for the AeroPulse API (mirrors services/api/app/schemas).
 * Every response is validated; a contract drift surfaces as an explicit error state
 * instead of silently rendering wrong numbers.
 */
import { z } from "zod";

const ts = z.string().datetime({ offset: true });
const tsN = ts.nullable();

export const SourceHealth = z.enum(["healthy", "delayed", "stale", "unavailable"]);
export const AirportStatus = z.enum(["critical", "warning", "weather", "normal", "unknown"]);
export const WeatherRisk = z.enum(["low", "elevated", "high", "severe", "unknown"]);
export type SourceHealth = z.infer<typeof SourceHealth>;
export type AirportStatus = z.infer<typeof AirportStatus>;
export type WeatherRisk = z.infer<typeof WeatherRisk>;

export const Meta = z.object({
  generated_at: ts,
  page: z.number().nullable().optional(),
  page_size: z.number().nullable().optional(),
  total: z.number().nullable().optional(),
  total_pages: z.number().nullable().optional(),
});
export type Meta = z.infer<typeof Meta>;

export const envelope = <T extends z.ZodType>(data: T) => z.object({ data, meta: Meta });

export const SourceFreshness = z.object({
  source: z.string(),
  display_name: z.string(),
  source_url: z.string(),
  health: SourceHealth,
  expected_interval_seconds: z.number(),
  last_attempt_at: tsN,
  last_success_at: tsN,
  last_failure_at: tsN,
  last_error: z.string().nullable(),
  consecutive_failures: z.number(),
  last_source_published_at: tsN,
  last_observation_at: tsN,
  last_record_count: z.number().nullable(),
  age_seconds: z.number().nullable(),
  thresholds_seconds: z.record(z.string(), z.number()),
  limitations: z.string(),
});
export type SourceFreshness = z.infer<typeof SourceFreshness>;

export const IngestionRun = z.object({
  id: z.number(),
  job: z.string(),
  trigger: z.string(),
  status: z.string(),
  started_at: ts,
  finished_at: tsN,
  records_fetched: z.number(),
  records_inserted: z.number(),
  records_updated: z.number(),
  records_rejected: z.number(),
  error_message: z.string().nullable(),
});
export type IngestionRun = z.infer<typeof IngestionRun>;

export const QualityCheck = z.object({
  source: z.string(),
  check_name: z.string(),
  status: z.string(),
  observed_value: z.number().nullable(),
  threshold: z.string().nullable(),
  message: z.string().nullable(),
  checked_at: ts,
});

export const SystemStatus = z.object({
  overall: SourceHealth,
  sources: z.array(SourceFreshness),
  recent_runs: z.array(IngestionRun),
  latest_quality: z.array(QualityCheck),
});
export type SystemStatus = z.infer<typeof SystemStatus>;

export const WeatherObservation = z.object({
  station_icao: z.string(),
  observed_at: ts,
  source_published_at: tsN,
  ingested_at: ts,
  metar_type: z.string(),
  raw_text: z.string(),
  temperature_c: z.number().nullable(),
  dewpoint_c: z.number().nullable(),
  wind_dir_deg: z.number().nullable(),
  wind_dir_variable: z.boolean(),
  wind_speed_kt: z.number().nullable(),
  wind_gust_kt: z.number().nullable(),
  visibility_sm: z.number().nullable(),
  visibility_text: z.string().nullable(),
  visibility_is_lower_bound: z.boolean(),
  altimeter_hpa: z.number().nullable(),
  ceiling_ft: z.number().nullable(),
  cloud_layers: z.array(z.object({ cover: z.string().nullable(), base_ft: z.number().nullable() })),
  wx_string: z.string().nullable(),
  flight_category: z.string().nullable(),
  flight_category_source: z.string(),
  is_stale: z.boolean(),
});
export type WeatherObservation = z.infer<typeof WeatherObservation>;

export const ForecastPeriod = z.object({
  seq: z.number(),
  time_from: ts,
  time_to: ts,
  change_indicator: z.string().nullable(),
  probability: z.number().nullable(),
  wind_dir_deg: z.number().nullable(),
  wind_speed_kt: z.number().nullable(),
  wind_gust_kt: z.number().nullable(),
  visibility_sm: z.number().nullable(),
  visibility_text: z.string().nullable(),
  wx_string: z.string().nullable(),
  ceiling_ft: z.number().nullable(),
  flight_category: z.string().nullable(),
});
export type ForecastPeriod = z.infer<typeof ForecastPeriod>;

export const Forecast = z.object({
  station_icao: z.string(),
  issued_at: ts,
  valid_from: ts,
  valid_to: ts,
  raw_text: z.string(),
  is_amendment: z.boolean(),
  ingested_at: ts,
  periods: z.array(ForecastPeriod),
});
export type Forecast = z.infer<typeof Forecast>;

export const WeatherHour = z.object({
  hour_utc: ts,
  observations: z.number(),
  avg_temperature_c: z.number().nullable(),
  max_wind_speed_kt: z.number().nullable(),
  max_wind_gust_kt: z.number().nullable(),
  min_visibility_sm: z.number().nullable(),
  min_ceiling_ft: z.number().nullable(),
  worst_flight_category: z.string().nullable(),
});
export type WeatherHour = z.infer<typeof WeatherHour>;

export const AirportWeather = z.object({
  airport: z.string(),
  observations: z.array(WeatherObservation),
  hourly: z.array(WeatherHour),
  forecast: Forecast.nullable(),
});
export type AirportWeather = z.infer<typeof AirportWeather>;

export const Advisory = z.object({
  id: z.number(),
  event_key: z.string(),
  airport_code: z.string(),
  airport_iata: z.string().nullable(),
  advisory_type: z.string(),
  scope: z.string(),
  reason: z.string().nullable(),
  text: z.string().nullable(),
  starts_at: tsN,
  ends_at: tsN,
  source_updated_at: tsN,
  avg_delay_minutes: z.number().nullable(),
  min_delay_minutes: z.number().nullable(),
  max_delay_minutes: z.number().nullable(),
  trend: z.string().nullable(),
  probability_of_extension: z.string().nullable(),
  advisory_url: z.string().nullable(),
  details: z.record(z.string(), z.unknown()),
  source_feed: z.string(),
  first_seen_at: ts,
  last_seen_at: ts,
  cleared_at: tsN,
  is_active: z.boolean(),
});
export type Advisory = z.infer<typeof Advisory>;

export const OperationalEvent = z.object({
  id: z.number(),
  advisory_id: z.number(),
  event_type: z.string(),
  airport_code: z.string(),
  advisory_type: z.string(),
  detected_at: ts,
  source_updated_at: tsN,
  changes: z.record(z.string(), z.unknown()),
});
export type OperationalEvent = z.infer<typeof OperationalEvent>;

export const AdvisoryDetail = Advisory.extend({
  timeline: z.array(OperationalEvent),
  source_url: z.string(),
});
export type AdvisoryDetail = z.infer<typeof AdvisoryDetail>;

export const AirportSummary = z.object({
  iata_code: z.string(),
  icao_code: z.string(),
  name: z.string(),
  city: z.string(),
  state: z.string(),
  latitude: z.number(),
  longitude: z.number(),
  timezone: z.string(),
  status: AirportStatus,
  status_reason: z.string(),
  weather_risk: WeatherRisk,
  weather_observed_at: tsN,
  weather_is_stale: z.boolean(),
  flight_category: z.string().nullable(),
  visibility_sm: z.number().nullable(),
  ceiling_ft: z.number().nullable(),
  wind_speed_kt: z.number().nullable(),
  wind_gust_kt: z.number().nullable(),
  temperature_c: z.number().nullable(),
  wx_string: z.string().nullable(),
  active_advisories: z.number(),
  has_ground_stop: z.boolean(),
  has_ground_delay_program: z.boolean(),
  has_full_closure: z.boolean(),
  has_reported_delay: z.boolean(),
  has_partial_closure: z.boolean(),
});
export type AirportSummary = z.infer<typeof AirportSummary>;

export const AirportDetail = AirportSummary.extend({
  elevation_ft: z.number().nullable(),
  weather_risk_factors: z.array(z.string()),
  latest_weather: WeatherObservation.nullable(),
  active_advisory_list: z.array(Advisory),
  forecast: Forecast.nullable(),
  runway_config: z
    .object({
      source_timestamp: ts,
      arrival_runway_config: z.string().nullable(),
      departure_runway_config: z.string().nullable(),
      arrival_rate: z.number().nullable(),
    })
    .nullable(),
});
export type AirportDetail = z.infer<typeof AirportDetail>;

const CategoryCount = z.object({ category: z.string(), airports: z.number() });

export const OperationsSummary = z.object({
  monitored_airports: z.number(),
  airports_with_active_advisories: z.number(),
  airports_with_disruptions: z.number(),
  active_ground_stops: z.number(),
  active_ground_delay_programs: z.number(),
  active_full_closures: z.number(),
  active_reported_delays: z.number(),
  active_partial_closures: z.number(),
  status_counts: z.record(z.string(), z.number()),
  flight_categories: z.array(CategoryCount),
  changes_last_hour: z.number(),
  recent_changes: z.array(OperationalEvent),
  faa_health: SourceHealth,
  weather_health: SourceHealth,
  faa_last_success_at: tsN,
  weather_last_success_at: tsN,
  latest_observation_at: tsN,
});
export type OperationsSummary = z.infer<typeof OperationsSummary>;

const Extreme = z.object({ airport: z.string(), value: z.number(), observed_at: ts });

export const WeatherOverview = z.object({
  airports: z.array(AirportSummary),
  flight_categories: z.array(CategoryCount),
  risk_counts: z.record(z.string(), z.number()),
  lowest_visibility: z.array(Extreme),
  strongest_wind: z.array(Extreme),
  lowest_ceiling: z.array(Extreme),
  weather_health: SourceHealth,
  advisory_weather_overlap: z.array(z.string()),
});
export type WeatherOverview = z.infer<typeof WeatherOverview>;

export const WeatherTrendSeries = z.object({ airport: z.string(), hourly: z.array(WeatherHour) });
export type WeatherTrendSeries = z.infer<typeof WeatherTrendSeries>;

// --------------------------------------------------------------------------- historical (BTS)

export const PerfRow = z.object({
  flights: z.number(),
  cancelled: z.number(),
  diverted: z.number(),
  delayed_15: z.number(),
  ontime_rate: z.number().nullable(),
  cancel_rate: z.number().nullable(),
  avg_delay_min: z.number().nullable(),
});
export type PerfRow = z.infer<typeof PerfRow>;

const Comparison = z.object({
  ontime_rate: z.number().nullable(),
  cancel_rate: z.number().nullable(),
  avg_delay_min: z.number().nullable(),
  flights: z.number().nullable(),
});
const Bucket = z.object({ key: z.string(), value: z.number() });
const dateOnly = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

export const Analytics = z.object({
  available: z.boolean(),
  direction: z.enum(["arrival", "departure"]),
  coverage: z.object({
    first_month: dateOnly.nullable(),
    last_month: dateOnly.nullable(),
    months_loaded: z.number(),
    selected_start: dateOnly.nullable(),
    selected_end: dateOnly.nullable(),
    source: z.string(),
    lag_note: z.string(),
  }),
  totals: PerfRow.nullable(),
  previous_year: Comparison.nullable(),
  network: Comparison.nullable().optional(),
  monthly: z.array(PerfRow.extend({ month: dateOnly })),
  airports: z.array(PerfRow.extend({ airport: z.string(), name: z.string(), rank_ontime: z.number() })),
  causes_minutes: z.array(Bucket),
  cancellation_causes: z.array(Bucket),
  delay_distribution: z.array(Bucket),
  day_of_week: z.array(PerfRow.extend({ iso_dow: z.number() })),
  hourly: z.array(PerfRow.extend({ hour_local: z.number() })),
  carriers: z.array(PerfRow.extend({ carrier_code: z.string(), carrier_name: z.string() })),
  airport_monthly: z.array(
    z.object({
      airport: z.string(),
      month: dateOnly,
      flights: z.number(),
      ontime_rate: z.number().nullable(),
      avg_delay_min: z.number().nullable(),
    }),
  ),
});
export type Analytics = z.infer<typeof Analytics>;

// --------------------------------------------------------------------------- risk (derived)

export const RiskComponent = z.object({
  key: z.string(),
  label: z.string(),
  points: z.number(),
  max_points: z.number(),
  detail: z.string(),
  source: z.string(),
});
export type RiskComponent = z.infer<typeof RiskComponent>;

export const RiskScore = z.object({
  airport_iata: z.string(),
  name: z.string().nullable().optional(),
  computed_at: ts,
  method_version: z.string(),
  score: z.number(),
  category: z.enum(["low", "moderate", "elevated", "high"]),
  components: z.array(RiskComponent),
  missing_inputs: z.array(z.string()),
  model_version: z.string().nullable(),
  model_probability: z.number().nullable(),
  model_contributions: z.array(z.record(z.string(), z.unknown())).nullable(),
  inputs_as_of: z.record(z.string(), z.unknown()),
});
export type RiskScore = z.infer<typeof RiskScore>;

export const RiskOverview = z.object({
  method_version: z.string(),
  computed_at: tsN,
  is_stale: z.boolean(),
  category_counts: z.record(z.string(), z.number()),
  airports: z.array(RiskScore),
  model: z.record(z.string(), z.unknown()).nullable(),
  disclaimer: z.string(),
});
export type RiskOverview = z.infer<typeof RiskOverview>;

export const AirportRisk = z.object({
  latest: RiskScore.nullable(),
  history: z.array(z.object({ computed_at: ts, score: z.number(), category: z.string(), model_probability: z.number().nullable() })),
});
export type AirportRisk = z.infer<typeof AirportRisk>;
