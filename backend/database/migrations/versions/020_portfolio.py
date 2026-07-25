"""Add portfolio tables: portfolios, portfolio_accounts, allocation_rules, portfolio_positions, portfolio_statistics.

Revision ID: 020_portfolio
Create Date: 2026-07-24
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "020_portfolio"
down_revision: Union[str, None] = "019_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("portfolios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), server_default=""),
        sa.Column("total_capital", sa.Float(), server_default="0.0"),
        sa.Column("allocated_capital", sa.Float(), server_default="0.0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("config_json", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("name"),
    )
    op.create_index("ix_pf_status", "portfolios", ["status"])

    op.create_table("portfolio_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("account_type", sa.String(20), server_default="paper"),
        sa.Column("name", sa.String(100), server_default=""),
        sa.Column("allocation_pct", sa.Float(), server_default="0.0"),
        sa.Column("allocation_method", sa.String(20), server_default="equal"),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), server_default="true"),
        sa.Column("balance", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pa_portfolio", "portfolio_accounts", ["portfolio_id"])

    op.create_table("allocation_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("parameter", sa.Float(), server_default="0.0"),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ar_portfolio", "allocation_rules", ["portfolio_id"])

    op.create_table("portfolio_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("total_quantity", sa.Integer(), server_default="0"),
        sa.Column("avg_entry_price", sa.Float(), server_default="0.0"),
        sa.Column("current_price", sa.Float(), server_default="0.0"),
        sa.Column("unrealized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pp_portfolio", "portfolio_positions", ["portfolio_id"])

    op.create_table("portfolio_statistics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("total_equity", sa.Float(), server_default="0.0"),
        sa.Column("daily_pnl", sa.Float(), server_default="0.0"),
        sa.Column("unrealized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("realized_pnl", sa.Float(), server_default="0.0"),
        sa.Column("drawdown_pct", sa.Float(), server_default="0.0"),
        sa.Column("exposure", sa.Float(), server_default="0.0"),
        sa.Column("capital_utilization", sa.Float(), server_default="0.0"),
        sa.Column("account_count", sa.Integer(), server_default="0"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ps_portfolio", "portfolio_statistics", ["portfolio_id"])
    op.create_index("ix_ps_timestamp", "portfolio_statistics", ["timestamp"])


def downgrade() -> None:
    op.drop_table("portfolio_statistics")
    op.drop_table("portfolio_positions")
    op.drop_table("allocation_rules")
    op.drop_table("portfolio_accounts")
    op.drop_table("portfolios")
