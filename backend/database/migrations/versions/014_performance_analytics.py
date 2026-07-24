"""Add analytics tables: analytics_reports, strategy_comparisons.

Revision ID: 014
Create Date: 2026-07-24
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "014_performance_analytics"
down_revision: Union[str, None] = "013_backtesting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("report_type", sa.String(50), server_default="full"),
        sa.Column("metrics_json", sa.String(10000), server_default="{}"),
        sa.Column("charts_json", sa.String(20000), server_default="{}"),
        sa.Column("summary_json", sa.String(5000), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ar_run", "analytics_reports", ["run_id"])

    op.create_table(
        "strategy_comparisons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_ids", sa.String(2000), server_default="[]"),
        sa.Column("comparison_json", sa.String(20000), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("strategy_comparisons")
    op.drop_table("analytics_reports")
