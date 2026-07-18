"""Add market_structure_events table.

Revision ID: 002
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "002_market_structure"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_structure_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("price_level", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("parent_swing_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mse_instrument", "market_structure_events", ["instrument_id"],
    )
    op.create_index(
        "ix_mse_timeframe", "market_structure_events", ["timeframe"],
    )
    op.create_index(
        "ix_mse_timestamp", "market_structure_events", ["bar_timestamp"],
    )
    op.create_index(
        "ix_mse_event_type", "market_structure_events", ["event_type"],
    )
    op.create_index(
        "ix_mse_lookup",
        "market_structure_events",
        ["instrument_id", "timeframe", "event_type"],
    )


def downgrade() -> None:
    op.drop_table("market_structure_events")
