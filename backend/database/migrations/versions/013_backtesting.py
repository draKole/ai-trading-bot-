"""Add backtesting tables: backtest_runs, backtest_trades, backtest_metrics.

Revision ID: 013
Create Date: 2026-07-24
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "013_backtesting"
down_revision: Union[str, None] = "012_replay"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("total_bars", sa.Integer(), server_default="0"),
        sa.Column("config_json", sa.String(5000), nullable=True),
        sa.Column("metrics_json", sa.String(5000), nullable=True),
        sa.Column("equity_curve_json", sa.String(20000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_br_instrument", "backtest_runs", ["instrument"])
    op.create_index("ix_br_status", "backtest_runs", ["status"])

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1"),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("stop_price", sa.Float(), server_default="0.0"),
        sa.Column("risk", sa.Float(), server_default="0.0"),
        sa.Column("r_multiple", sa.Float(), server_default="0.0"),
        sa.Column("pnl", sa.Float(), server_default="0.0"),
        sa.Column("duration_seconds", sa.Integer(), server_default="0"),
        sa.Column("exit_reason", sa.String(50), server_default=""),
        sa.Column("strategy_version", sa.String(20), server_default="1.0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bt_run", "backtest_trades", ["run_id"])

    op.create_table(
        "backtest_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("net_profit", sa.Float(), server_default="0.0"),
        sa.Column("gross_profit", sa.Float(), server_default="0.0"),
        sa.Column("gross_loss", sa.Float(), server_default="0.0"),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("winning_trades", sa.Integer(), server_default="0"),
        sa.Column("losing_trades", sa.Integer(), server_default="0"),
        sa.Column("breakeven_trades", sa.Integer(), server_default="0"),
        sa.Column("win_rate", sa.Float(), server_default="0.0"),
        sa.Column("loss_rate", sa.Float(), server_default="0.0"),
        sa.Column("profit_factor", sa.Float(), server_default="0.0"),
        sa.Column("average_win", sa.Float(), server_default="0.0"),
        sa.Column("average_loss", sa.Float(), server_default="0.0"),
        sa.Column("average_r", sa.Float(), server_default="0.0"),
        sa.Column("expectancy", sa.Float(), server_default="0.0"),
        sa.Column("max_drawdown", sa.Float(), server_default="0.0"),
        sa.Column("max_drawdown_pct", sa.Float(), server_default="0.0"),
        sa.Column("max_consecutive_wins", sa.Integer(), server_default="0"),
        sa.Column("max_consecutive_losses", sa.Integer(), server_default="0"),
        sa.Column("average_trade_duration_seconds", sa.Float(), server_default="0.0"),
        sa.Column("long_trades", sa.Integer(), server_default="0"),
        sa.Column("long_wins", sa.Integer(), server_default="0"),
        sa.Column("long_pnl", sa.Float(), server_default="0.0"),
        sa.Column("short_trades", sa.Integer(), server_default="0"),
        sa.Column("short_wins", sa.Integer(), server_default="0"),
        sa.Column("short_pnl", sa.Float(), server_default="0.0"),
        sa.Column("largest_winner", sa.Float(), server_default="0.0"),
        sa.Column("largest_loser", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )


def downgrade() -> None:
    op.drop_table("backtest_metrics")
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
