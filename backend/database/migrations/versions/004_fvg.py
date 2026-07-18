"""Add fair_value_gaps and fvg_lifecycle_events tables.

Revision ID: 004
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "004_fvg"
down_revision: Union[str, None] = "003_liquidity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fair_value_gaps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("upper_bound", sa.Float(), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=False),
        sa.Column("midpoint", sa.Float(), nullable=False),
        sa.Column("gap_size", sa.Float(), nullable=False),
        sa.Column("gap_size_pct", sa.Float(), nullable=False),
        sa.Column("fill_percentage", sa.Float(), server_default="0.0"),
        sa.Column("creation_bar_index", sa.Integer(), nullable=False),
        sa.Column("creation_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_touch_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_touch_bar_index", sa.Integer(), nullable=True),
        sa.Column("mitigation_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mitigation_bar_index", sa.Integer(), nullable=True),
        sa.Column("invalidation_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_bar_index", sa.Integer(), nullable=True),
        sa.Column("candle_1_high", sa.Float(), server_default="0.0"),
        sa.Column("candle_1_low", sa.Float(), server_default="0.0"),
        sa.Column("candle_2_high", sa.Float(), server_default="0.0"),
        sa.Column("candle_2_low", sa.Float(), server_default="0.0"),
        sa.Column("candle_3_high", sa.Float(), server_default="0.0"),
        sa.Column("candle_3_low", sa.Float(), server_default="0.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fvg_instrument", "fair_value_gaps", ["instrument_id"])
    op.create_index("ix_fvg_timeframe", "fair_value_gaps", ["timeframe"])
    op.create_index("ix_fvg_direction", "fair_value_gaps", ["direction"])
    op.create_index("ix_fvg_status", "fair_value_gaps", ["status"])
    op.create_index("ix_fvg_creation_ts", "fair_value_gaps", ["creation_timestamp"])
    op.create_index(
        "ix_fvg_lookup",
        "fair_value_gaps",
        ["instrument_id", "timeframe", "direction", "status"],
    )

    op.create_table(
        "fvg_lifecycle_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fvg_id", sa.Integer(), nullable=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("bar_index", sa.Integer(), nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fill_percentage", sa.Float(), server_default="0.0"),
        sa.Column("fvg_direction", sa.String(10), nullable=True),
        sa.Column("fvg_upper", sa.Float(), nullable=True),
        sa.Column("fvg_lower", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fvg_event_fvg", "fvg_lifecycle_events", ["fvg_id"])
    op.create_index("ix_fvg_event_instrument", "fvg_lifecycle_events", ["instrument_id"])
    op.create_index("ix_fvg_event_type", "fvg_lifecycle_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("fvg_lifecycle_events")
    op.drop_table("fair_value_gaps")
