"""Add live trading tables: live_trading_sessions, live_orders, live_executions, broker_connection_logs.

Revision ID: 016
Create Date: 2026-07-24
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "016_live_broker"
down_revision: Union[str, None] = "015_paper_trading"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "live_trading_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("broker", sa.String(30), server_default="tradovate"),
        sa.Column("connection_state", sa.String(20), server_default="disconnected"),
        sa.Column("balance", sa.Float(), server_default="0.0"),
        sa.Column("buying_power", sa.Float(), server_default="0.0"),
        sa.Column("initial_balance", sa.Float(), server_default="100000.0"),
        sa.Column("realized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("unrealized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("config_json", sa.String(2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
    )
    op.create_index("ix_lts_account", "live_trading_sessions", ["account_id"])

    op.create_table(
        "live_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("live_trading_sessions.id"), nullable=False),
        sa.Column("broker_order_id", sa.String(50), server_default=""),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("filled_qty", sa.Integer(), server_default="0"),
        sa.Column("avg_fill_price", sa.Float(), server_default="0.0"),
        sa.Column("rejected_reason", sa.String(200), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lo_session", "live_orders", ["session_id"])
    op.create_index("ix_lo_status", "live_orders", ["status"])

    op.create_table(
        "live_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("live_trading_sessions.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("live_orders.id"), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("commission", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_le_session", "live_executions", ["session_id"])
    op.create_index("ix_le_order", "live_executions", ["order_id"])

    op.create_table(
        "broker_connection_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("live_trading_sessions.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("detail", sa.String(500), server_default=""),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bcl_session", "broker_connection_logs", ["session_id"])


def downgrade() -> None:
    op.drop_table("broker_connection_logs")
    op.drop_table("live_executions")
    op.drop_table("live_orders")
    op.drop_table("live_trading_sessions")
