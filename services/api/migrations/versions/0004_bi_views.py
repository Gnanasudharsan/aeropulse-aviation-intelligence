"""BI views (mirrors analytics/sql/bi_views.sql; a test keeps them identical).

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

BI_VIEWS_SQL = r"""
-- AeroPulse BI views over PostgreSQL (alternative to the Parquet export, e.g. for a
-- DirectQuery/Import connection through a gateway, or ad-hoc SQL analysis).
-- All measures are additive; compute rates as SUM(numerator) / SUM(denominator).

CREATE OR REPLACE VIEW bi_dim_airport AS
SELECT iata_code, icao_code, name, city, state, latitude, longitude, timezone
FROM airports WHERE is_monitored;

CREATE OR REPLACE VIEW bi_fact_airport_daily AS
SELECT airport_iata, flight_date, direction::text AS direction,
       flights, cancelled, diverted, ontime_den, ontime_num, delayed_15,
       cancel_carrier, cancel_weather, cancel_nas, cancel_security,
       bucket_early, bucket_0_14, bucket_15_29, bucket_30_59, bucket_60_119, bucket_120_plus,
       delay_sum_min, carrier_delay_min, weather_delay_min, nas_delay_min,
       security_delay_min, late_aircraft_delay_min
FROM airport_performance_daily;

-- Gold: monthly airport scorecard (rates recomputed from sums).
CREATE OR REPLACE VIEW gold_airport_monthly_scorecard AS
SELECT airport_iata,
       date_trunc('month', flight_date)::date               AS month,
       direction::text                                      AS direction,
       sum(flights)                                         AS flights,
       sum(ontime_num)::numeric / nullif(sum(ontime_den), 0) AS ontime_rate,
       sum(cancelled)::numeric / nullif(sum(flights), 0)     AS cancel_rate,
       sum(delay_sum_min)::numeric / nullif(sum(ontime_den), 0) AS avg_delay_min,
       sum(weather_delay_min)::numeric
         / nullif(sum(carrier_delay_min + weather_delay_min + nas_delay_min
                      + security_delay_min + late_aircraft_delay_min), 0) AS weather_share_of_cause_minutes
FROM airport_performance_daily
GROUP BY 1, 2, 3;

-- Gold: disruption event timeline from live operations (FAA advisories).
CREATE OR REPLACE VIEW gold_disruption_timeline AS
SELECT a.airport_code, a.advisory_type, a.scope, a.starts_at, a.ends_at,
       a.first_seen_at, a.cleared_at,
       coalesce(a.cleared_at, now()) - a.first_seen_at AS observed_duration,
       a.avg_delay_minutes, a.reason
FROM faa_advisories a
WHERE a.advisory_type IN ('ground_stop', 'ground_delay_program', 'airport_closure',
                          'arrival_delay', 'departure_delay');

-- Data freshness and source reliability (last 7 days of runs).
CREATE OR REPLACE VIEW gold_source_reliability AS
SELECT job,
       count(*)                                              AS runs,
       count(*) FILTER (WHERE status = 'success')            AS successful,
       count(*) FILTER (WHERE status = 'partial')            AS partial,
       count(*) FILTER (WHERE status = 'failed')             AS failed,
       round(100.0 * count(*) FILTER (WHERE status <> 'failed') / nullif(count(*), 0), 2) AS availability_pct,
       max(finished_at) FILTER (WHERE status <> 'failed')    AS last_success
FROM ingestion_runs
WHERE started_at > now() - interval '7 days'
GROUP BY job;
"""

VIEWS = [
    "gold_source_reliability",
    "gold_disruption_timeline",
    "gold_airport_monthly_scorecard",
    "bi_fact_airport_daily",
    "bi_dim_airport",
]


def upgrade() -> None:
    op.execute(BI_VIEWS_SQL)


def downgrade() -> None:
    for v in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {v}")
