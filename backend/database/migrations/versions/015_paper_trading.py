"""Add paper trading tables: paper_trading_sessions, paper_orders, paper_positions, paper_executions.

Revision ID: 015
Create Date: 2026-07-24
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "015_paper_trading"
down_revision: Union[str, None] = "014_performance_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_trading_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), server_default="Default Paper Account"),
        sa.Column("balance", sa.Float(), server_default="100000.0"),
        sa.Column("buying_power", sa.Float(), server_default="100000.0"),
        sa.Column("initial_balance", sa.Float(), server_default="100000.0"),
        sa.Column("realized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("unrealized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("status", sa.String(20), server_default="stopped"),
        sa.Column("config_json", sa.String(2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
    )
    op.create_index("ix_pts_account", "paper_trading_sessions", ["account_id"])
    op.create_index("ix_pts_status", "paper_trading_sessions", ["status"])

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("paper_trading_sessions.id"), nullable=False),
        sa.Column("order_type", sa.String(20), server_default="market"),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("filled_qty", sa.Integer(), server_default="0"),
        sa.Column("fill_price", sa.Float(), nullable=True),
        sa.Column("slippage", sa.Float(), server_default="0.0"),
        sa.Column("commission", sa.Float(), server_default="0.0"),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_po_session", "paper_orders", ["session_id"])
    op.create_index("ix_po_status", "paper_orders", ["status"])

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("paper_trading_sessions.id"), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_entry_price", sa.Float(), server_default="0.0"),
        sa.Column("current_price", sa.Float(), server_default="0.0"),
        sa.Column("unrealized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pp_session", "paper_positions", ["session_id"])
    op.create_index("ix_pp_status", "paper_positions", ["status"])

    op.create_table(
        "paper_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("paper_trading_sessions.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("paper_orders.id"), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("commission", sa.Float(), server_default="0.0"),
        sa.Column("slippage", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pe_session", "paper_executions", ["session_id"])
    op.create_index("ix_pe_order", "paper_executions", ["order_id"])


def downgrade() -> None:
    op.drop_table("paper_executions")
    op.drop_table("paper_positions")
    op.drop_table("paper_orders")
    op.drop_table("paper_trading_sessions")
