"""Historical BTS on-time performance (aggregated facts + lineage).

Revision ID: 0003
Revises: 0002

Grain and additivity are documented in analytics/metric_definitions. All measure columns
are additive counts/sums so any rate can be recomputed at any aggregation level
(never average pre-computed averages).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _measures() -> list[sa.Column]:
    cols = [
        "flights", "cancelled", "diverted", "ontime_den", "ontime_num", "delayed_15",
        "cancel_carrier", "cancel_weather", "cancel_nas", "cancel_security",
        "bucket_early", "bucket_0_14", "bucket_15_29", "bucket_30_59", "bucket_60_119",
        "bucket_120_plus",
    ]
    out = [sa.Column(c, sa.Integer, nullable=False, server_default="0") for c in cols]
    out += [
        sa.Column(c, sa.BigInteger, nullable=False, server_default="0")
        for c in (
            "delay_sum_min", "carrier_delay_min", "weather_delay_min", "nas_delay_min",
            "security_delay_min", "late_aircraft_delay_min",
        )
    ]
    return out


def upgrade() -> None:
    direction = sa.Enum("departure", "arrival", name="flight_direction")

    op.create_table(
        "carriers",
        sa.Column("carrier_code", sa.String(3), primary_key=True),
        sa.Column("carrier_name", sa.String(120), nullable=False),
    )
    op.create_table(
        "historical_loads",
        sa.Column("year_month", sa.Date, primary_key=True),
        sa.Column("source_file", sa.Text, nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("rows_read", sa.Integer, nullable=False),
        sa.Column("rows_monitored", sa.Integer, nullable=False),
        sa.Column("quality", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "airport_performance_daily",
        sa.Column("airport_iata", sa.String(4), sa.ForeignKey("airports.iata_code"), nullable=False),
        sa.Column("flight_date", sa.Date, nullable=False),
        sa.Column("direction", direction, nullable=False),
        *_measures(),
        sa.PrimaryKeyConstraint("airport_iata", "flight_date", "direction"),
    )
    op.create_index("ix_apd_date", "airport_performance_daily", ["flight_date"])
    op.create_table(
        "airport_performance_hourly",
        sa.Column("airport_iata", sa.String(4), sa.ForeignKey("airports.iata_code"), nullable=False),
        sa.Column("year_month", sa.Date, nullable=False),
        sa.Column("direction", direction, nullable=False),
        sa.Column("hour_local", sa.SmallInteger, nullable=False),
        *_measures(),
        sa.PrimaryKeyConstraint("airport_iata", "year_month", "direction", "hour_local"),
        sa.CheckConstraint("hour_local BETWEEN 0 AND 23", name="hour_range"),
    )
    op.create_table(
        "carrier_performance_monthly",
        sa.Column("airport_iata", sa.String(4), sa.ForeignKey("airports.iata_code"), nullable=False),
        sa.Column("year_month", sa.Date, nullable=False),
        sa.Column("direction", direction, nullable=False),
        sa.Column("carrier_code", sa.String(3), nullable=False),
        *_measures(),
        sa.PrimaryKeyConstraint("airport_iata", "year_month", "direction", "carrier_code"),
    )


def downgrade() -> None:
    for t in ("carrier_performance_monthly", "airport_performance_hourly", "airport_performance_daily",
              "historical_loads", "carriers"):
        op.drop_table(t)
    sa.Enum(name="flight_direction").drop(op.get_bind(), checkfirst=True)
