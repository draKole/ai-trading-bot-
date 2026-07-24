"""Add replay tables: replay_sessions, replay_snapshots, replay_events.

Revision ID: 012
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "012_replay"
down_revision: Union[str, None] = "011_trade_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "replay_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(30), server_default="candle_by_candle"),
        sa.Column("status", sa.String(20), server_default="idle"),
        sa.Column("bar_count", sa.Integer(), server_default="0"),
        sa.Column("bar_index", sa.Integer(), server_default="0"),
        sa.Column("current_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_json", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rs_instrument", "replay_sessions", ["instrument"])
    op.create_index("ix_rs_status", "replay_sessions", ["status"])

    op.create_table(
        "replay_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("replay_id", sa.Integer(), sa.ForeignKey("replay_sessions.id"), nullable=False),
        sa.Column("bar_index", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candle_json", sa.String(1000), nullable=False),
        sa.Column("summary_json", sa.String(5000), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rsnap_replay", "replay_snapshots", ["replay_id"])

    op.create_table(
        "replay_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("replay_id", sa.Integer(), sa.ForeignKey("replay_sessions.id"), nullable=False),
        sa.Column("bar_index", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("engine_source", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("entity_ids_json", sa.String(2000), server_default="[]"),
        sa.Column("detail", sa.String(500), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revt_replay", "replay_events", ["replay_id"])


def downgrade() -> None:
    op.drop_table("replay_events")
    op.drop_table("replay_snapshots")
    op.drop_table("replay_sessions")
