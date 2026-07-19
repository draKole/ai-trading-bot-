"""Add order_blocks and ob_lifecycle_events tables.

Revision ID: 005
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "005_order_block"
down_revision: Union[str, None] = "004_fvg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_blocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("status", sa.String(25), nullable=False),
        sa.Column("upper_bound", sa.Float(), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=False),
        sa.Column("midpoint", sa.Float(), nullable=False),
        sa.Column("block_size", sa.Float(), nullable=False),
        sa.Column("block_size_pct", sa.Float(), nullable=False),
        sa.Column("mitigation_percentage", sa.Float(), server_default="0.0"),
        sa.Column("origin_candle_index", sa.Integer(), nullable=False),
        sa.Column("creation_bar_index", sa.Integer(), nullable=False),
        sa.Column("creation_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_touch_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_touch_bar_index", sa.Integer(), nullable=True),
        sa.Column("mitigation_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mitigation_bar_index", sa.Integer(), nullable=True),
        sa.Column("invalidation_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_bar_index", sa.Integer(), nullable=True),
        sa.Column("related_ms_event_id", sa.Integer(), nullable=True),
        sa.Column("related_liquidity_ids", sa.JSON(), nullable=True),
        sa.Column("related_fvg_ids", sa.JSON(), nullable=True),
        sa.Column("origin_open", sa.Float(), server_default="0.0"),
        sa.Column("origin_high", sa.Float(), server_default="0.0"),
        sa.Column("origin_low", sa.Float(), server_default="0.0"),
        sa.Column("origin_close", sa.Float(), server_default="0.0"),
        sa.Column("origin_volume", sa.Float(), server_default="0.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ob_instrument", "order_blocks", ["instrument_id"])
    op.create_index("ix_ob_timeframe", "order_blocks", ["timeframe"])
    op.create_index("ix_ob_direction", "order_blocks", ["direction"])
    op.create_index("ix_ob_status", "order_blocks", ["status"])
    op.create_index("ix_ob_creation_ts", "order_blocks", ["creation_timestamp"])
    op.create_index(
        "ix_ob_lookup",
        "order_blocks",
        ["instrument_id", "timeframe", "direction", "status"],
    )

    op.create_table(
        "ob_lifecycle_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ob_id", sa.Integer(), nullable=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("event_type", sa.String(25), nullable=False),
        sa.Column("bar_index", sa.Integer(), nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mitigation_percentage", sa.Float(), server_default="0.0"),
        sa.Column("ob_direction", sa.String(10), nullable=True),
        sa.Column("ob_upper", sa.Float(), nullable=True),
        sa.Column("ob_lower", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ob_event_ob", "ob_lifecycle_events", ["ob_id"])
    op.create_index("ix_ob_event_instrument", "ob_lifecycle_events", ["instrument_id"])
    op.create_index("ix_ob_event_type", "ob_lifecycle_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("ob_lifecycle_events")
    op.drop_table("order_blocks")
