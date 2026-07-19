"""Add smt_events and smt_pair_configs tables.

Revision ID: 006
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "006_smt"
down_revision: Union[str, None] = "005_order_block"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "smt_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("primary_instrument", sa.String(20), nullable=False),
        sa.Column("secondary_instrument", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("primary_swing_type", sa.String(15), nullable=False),
        sa.Column("primary_swing_price", sa.Float(), nullable=False),
        sa.Column("primary_swing_bar_index", sa.Integer(), nullable=False),
        sa.Column("primary_swing_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("primary_prior_swing_price", sa.Float(), nullable=True),
        sa.Column("primary_ms_event_id", sa.Integer(), nullable=True),
        sa.Column("secondary_swing_type", sa.String(15), nullable=False),
        sa.Column("secondary_swing_price", sa.Float(), nullable=False),
        sa.Column("secondary_swing_bar_index", sa.Integer(), nullable=False),
        sa.Column("secondary_swing_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("secondary_prior_swing_price", sa.Float(), nullable=True),
        sa.Column("secondary_ms_event_id", sa.Integer(), nullable=True),
        sa.Column("divergence_pct", sa.Float(), server_default="0.0"),
        sa.Column("timestamp_delta_seconds", sa.Float(), server_default="0.0"),
        sa.Column("detection_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detection_bar_index", sa.Integer(), server_default="0"),
        sa.Column("related_liquidity_ids", sa.JSON(), nullable=True),
        sa.Column("related_fvg_ids", sa.JSON(), nullable=True),
        sa.Column("related_ob_ids", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_smt_primary", "smt_events", ["primary_instrument"])
    op.create_index("ix_smt_secondary", "smt_events", ["secondary_instrument"])
    op.create_index("ix_smt_timeframe", "smt_events", ["timeframe"])
    op.create_index("ix_smt_direction", "smt_events", ["direction"])
    op.create_index("ix_smt_detection_ts", "smt_events", ["detection_timestamp"])
    op.create_index(
        "ix_smt_pair_tf", "smt_events",
        ["primary_instrument", "secondary_instrument", "timeframe"],
    )

    op.create_table(
        "smt_pair_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("primary_instrument", sa.String(20), nullable=False),
        sa.Column("secondary_instrument", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("timestamp_tolerance_seconds", sa.Float(), server_default="300.0"),
        sa.Column("min_divergence_pct", sa.Float(), server_default="0.05"),
        sa.Column("enabled_timeframes", sa.JSON(), nullable=True),
        sa.Column("label", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("primary_instrument", "secondary_instrument"),
    )


def downgrade() -> None:
    op.drop_table("smt_pair_configs")
    op.drop_table("smt_events")
