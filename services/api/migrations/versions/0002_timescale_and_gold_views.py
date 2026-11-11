"""TimescaleDB (when available) and gold-layer views.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


GOLD_VIEWS = {
    # Latest METAR per airport (corrections with the same obs time: latest receipt wins).
    "v_latest_weather": """
        SELECT DISTINCT ON (w.airport_iata) w.*
        FROM weather_observations w
        ORDER BY w.airport_iata, w.observed_at DESC, w.source_published_at DESC NULLS LAST
    """,
    # Active = present in the latest successful poll (cleared_at IS NULL) and not past its end.
    "v_active_advisories": """
        SELECT a.*
        FROM faa_advisories a
        WHERE a.cleared_at IS NULL
          AND (a.ends_at IS NULL OR a.ends_at > now())
    """,
    # One row per monitored airport with advisory flags and the latest observation.
    "v_airport_status": """
        SELECT
            ap.iata_code, ap.icao_code, ap.name, ap.city, ap.state, ap.latitude, ap.longitude,
            ap.timezone,
            lw.observed_at           AS weather_observed_at,
            lw.flight_category,
            lw.visibility_sm, lw.ceiling_ft, lw.wind_speed_kt, lw.wind_gust_kt,
            lw.temperature_c, lw.wx_string,
            COALESCE(adv.n_active, 0)                AS active_advisories,
            COALESCE(adv.has_ground_stop, false)     AS has_ground_stop,
            COALESCE(adv.has_gdp, false)             AS has_ground_delay_program,
            COALESCE(adv.has_full_closure, false)    AS has_full_closure,
            COALESCE(adv.has_reported_delay, false)  AS has_reported_delay,
            COALESCE(adv.has_partial_closure, false) AS has_partial_closure,
            COALESCE(adv.has_deicing, false)         AS has_deicing
        FROM airports ap
        LEFT JOIN v_latest_weather lw ON lw.airport_iata = ap.iata_code
        LEFT JOIN (
            SELECT airport_code,
                   count(*) AS n_active,
                   bool_or(advisory_type = 'ground_stop') AS has_ground_stop,
                   bool_or(advisory_type = 'ground_delay_program') AS has_gdp,
                   bool_or(advisory_type IN ('airport_closure', 'closure_notam')
                           AND (scope = 'full'
                                OR (scope = 'daily_window' AND ap_in_daily_window(details, now()))))
                       AS has_full_closure,
                   bool_or(advisory_type IN ('arrival_delay', 'departure_delay'))
                       AS has_reported_delay,
                   bool_or(advisory_type = 'closure_notam' AND scope = 'partial')
                       AS has_partial_closure,
                   bool_or(advisory_type = 'deicing') AS has_deicing
            FROM v_active_advisories
            GROUP BY airport_code
        ) adv ON adv.airport_code = ap.iata_code
        WHERE ap.is_monitored
    """,
    # Hourly weather aggregates per airport (worst flight category in the hour).
    "v_weather_hourly": """
        SELECT
            airport_iata,
            date_trunc('hour', observed_at) AS hour_utc,
            count(*)                         AS observations,
            avg(temperature_c)               AS avg_temperature_c,
            max(wind_speed_kt)               AS max_wind_speed_kt,
            max(wind_gust_kt)                AS max_wind_gust_kt,
            min(visibility_sm)               AS min_visibility_sm,
            min(ceiling_ft)                  AS min_ceiling_ft,
            (ARRAY['VFR','MVFR','IFR','LIFR'])[max(
                CASE flight_category WHEN 'VFR' THEN 1 WHEN 'MVFR' THEN 2
                                     WHEN 'IFR' THEN 3 WHEN 'LIFR' THEN 4 END)]
                AS worst_flight_category
        FROM weather_observations
        GROUP BY airport_iata, date_trunc('hour', observed_at)
    """,
}


def upgrade() -> None:
    # TimescaleDB is optional (ADR-004): hypertable only where the extension exists.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
            CREATE EXTENSION IF NOT EXISTS timescaledb;
            PERFORM create_hypertable('weather_observations', 'observed_at',
                                      chunk_time_interval => INTERVAL '7 days',
                                      migrate_data => true, if_not_exists => true);
          END IF;
        END$$;
        """
    )
    # Recurring daily closure windows (e.g. curfews "DLY 0730-1415", UTC, may wrap midnight).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ap_in_daily_window(details jsonb, at timestamptz)
        RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
          WITH w AS (
            SELECT substr(details->'daily_window_utc'->>0, 1, 2)::int * 60
                     + substr(details->'daily_window_utc'->>0, 3, 2)::int AS s,
                   substr(details->'daily_window_utc'->>1, 1, 2)::int * 60
                     + substr(details->'daily_window_utc'->>1, 3, 2)::int AS e,
                   extract(hour FROM at AT TIME ZONE 'UTC')::int * 60
                     + extract(minute FROM at AT TIME ZONE 'UTC')::int AS m
            WHERE details ? 'daily_window_utc'
          )
          SELECT COALESCE((SELECT CASE WHEN s <= e THEN m >= s AND m < e
                                       ELSE m >= s OR m < e END FROM w), false)
        $$;
        """
    )
    for name, sql in GOLD_VIEWS.items():
        op.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")


def downgrade() -> None:
    for name in reversed(list(GOLD_VIEWS)):
        op.execute(f"DROP VIEW IF EXISTS {name} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS ap_in_daily_window(jsonb, timestamptz)")
