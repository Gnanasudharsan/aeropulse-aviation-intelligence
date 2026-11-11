"""Risk scores (versioned, explainable, persisted for trends).

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_scores",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("airport_iata", sa.String(4), sa.ForeignKey("airports.iata_code"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method_version", sa.String(32), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("components", postgresql.JSONB, nullable=False),
        sa.Column("missing_inputs", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("model_version", sa.String(64)),
        sa.Column("model_probability", sa.Float),
        sa.Column("model_contributions", postgresql.JSONB),
        sa.Column("inputs_as_of", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_risk_scores_airport_time", "risk_scores", ["airport_iata", "computed_at"])
    op.create_index("ix_risk_scores_time", "risk_scores", ["computed_at"])


def downgrade() -> None:
    op.drop_table("risk_scores")
