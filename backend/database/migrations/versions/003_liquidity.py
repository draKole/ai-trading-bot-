"""Add liquidity_levels and liquidity_events tables.

Revision ID: 003
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "003_liquidity"
down_revision: Union[str, None] = "002_market_structure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Liquidity Levels
    op.create_table(
        "liquidity_levels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("level_type", sa.String(30), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("source_bar_index", sa.Integer(), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lq_level_instrument", "liquidity_levels", ["instrument_id"])
    op.create_index("ix_lq_level_type", "liquidity_levels", ["level_type"])
    op.create_index("ix_lq_level_session", "liquidity_levels", ["session"])
    op.create_index("ix_lq_level_active", "liquidity_levels", ["is_active"])
    op.create_index(
        "ix_lq_level_lookup",
        "liquidity_levels",
        ["instrument_id", "timeframe", "level_type", "is_active"],
    )

    # Liquidity Events
    op.create_table(
        "liquidity_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("level_type", sa.String(30), nullable=False),
        sa.Column("level_price", sa.Float(), nullable=False),
        sa.Column("bar_index", sa.Integer(), nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bar_high", sa.Float(), nullable=False),
        sa.Column("bar_low", sa.Float(), nullable=False),
        sa.Column("bar_close", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("distance_pct", sa.Float(), server_default="0.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lq_event_instrument", "liquidity_events", ["instrument_id"])
    op.create_index("ix_lq_event_type", "liquidity_events", ["event_type"])
    op.create_index("ix_lq_event_timestamp", "liquidity_events", ["bar_timestamp"])
    op.create_index(
        "ix_lq_event_lookup",
        "liquidity_events",
        ["instrument_id", "timeframe", "event_type"],
    )


def downgrade() -> None:
    op.drop_table("liquidity_events")
    op.drop_table("liquidity_levels")
