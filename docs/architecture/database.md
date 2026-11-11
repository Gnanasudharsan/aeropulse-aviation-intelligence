# Database design

PostgreSQL 16. Schema is managed exclusively by Alembic (`services/api/migrations`).
All timestamps are `timestamptz` stored in UTC.

## Bronze

| Table | Grain | Key | Notes |
|---|---|---|---|
| `ingestion_runs` | one job execution | `id` | job, trigger (`schedule`/`startup`/`manual`/`http`), status (`running`/`success`/`partial`/`failed`), counts, error, JSON details (quality summary, feed used). |
| `raw_payloads` | one upstream HTTP response | `id` | source feed, URL, HTTP status, `fetched_at`, `source_published_at`, SHA-256 checksum, parse status. Payload body is stored only when its checksum differs from the previous payload of the same feed (`parse_status = 'unchanged'` otherwise). Failed fetches are recorded with `parse_status = 'fetch_failed'`. |

## Silver

| Table | Grain | Natural / unique key | Indexes |
|---|---|---|---|
| `airports` | airport | `iata_code` (PK), `icao_code` (unique) | — |
| `weather_observations` | one METAR/SPECI text | PK `(station_icao, observed_at, raw_hash)` | `(airport_iata, observed_at)`; **TimescaleDB hypertable** on `observed_at` (7-day chunks) when the extension exists |
| `weather_forecasts` | one TAF issuance | unique `(station_icao, issued_at, raw_hash)` | `(airport_iata, issued_at)` |
| `weather_forecast_periods` | one TAF change group | PK `(forecast_id, seq)` | — |
| `faa_advisories` | one FAA airport event across its lifetime | unique `event_key` | `airport_code`, `advisory_type`, `(cleared_at, advisory_type)` |
| `operational_events` | one detected lifecycle change (`created`/`updated`/`cleared`/`reopened`) | `id` | `detected_at`, `(airport_code, detected_at)` |
| `airport_configs` | runway configuration snapshot | PK `(airport_code, source_timestamp)` | — |
| `source_status` | upstream source | `source` | last attempt / success / failure, consecutive failures, last published & observation times |
| `data_quality_results` | one check in one run | `id` | `ingestion_run_id`, `checked_at` |

### Idempotency

* METAR: `INSERT … ON CONFLICT DO NOTHING` on the natural key. The METAR job requests a
  3-hour lookback each run, so missed runs are back-filled and re-delivered observations
  are counted as `duplicates_skipped`, never re-inserted.
* TAF: `ON CONFLICT DO NOTHING` on `(station, issued_at, raw_hash)`; amendments have new
  issue times and are stored as new rows.
* FAA: `event_key` = `faa:{type}:{upstream id}` when FAA supplies an id, otherwise a hash
  of airport/type/start(/text). A content hash decides whether a re-seen advisory changed.

## Gold views (migration `0002`)

| View | Purpose |
|---|---|
| `v_latest_weather` | Latest observation per airport (corrections with the same observation time: latest receipt wins). |
| `v_active_advisories` | `cleared_at IS NULL AND (ends_at IS NULL OR ends_at > now())`. |
| `v_airport_status` | One row per monitored airport: latest weather + advisory flags. Daily-window closures (e.g. curfews `DLY 0730-1415`) count as full closures only inside the window (`ap_in_daily_window`). |
| `v_weather_hourly` | Hourly aggregates per airport including the worst flight category in the hour. |

## Retention

| Data | Policy | Mechanism |
|---|---|---|
| `raw_payloads` | 7 days (`BRONZE_RETENTION_DAYS`) | worker job `purge_bronze`, daily 03:17 UTC |
| `weather_observations` | 400 days | sized for hourly trend charts; ~50 stations × ~30 obs/day ≈ 0.6 M rows/yr |
| `faa_advisories`, `operational_events` | indefinite | low volume; required for event history |
| `ingestion_runs`, `data_quality_results` | indefinite locally; 90 days on constrained hosted plans | manual/cron purge |
