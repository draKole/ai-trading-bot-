"""Add optimization tables: optimization_runs, parameter_sets, optimization_results, walk_forward_runs, monte_carlo_runs.

Revision ID: 021
Create Date: 2026-07-25
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "021_optimization"
down_revision: Union[str, None] = "020_portfolio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("optimization_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("total_combinations", sa.Integer(), server_default="0"),
        sa.Column("completed_combinations", sa.Integer(), server_default="0"),
        sa.Column("best_params_json", sa.String(2000), nullable=True),
        sa.Column("best_score", sa.Float(), server_default="0.0"),
        sa.Column("config_json", sa.String(5000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_or_status", "optimization_runs", ["status"])

    op.create_table("parameter_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("optimization_runs.id"), nullable=False),
        sa.Column("params_json", sa.String(2000), nullable=False),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("rank", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ps_run", "parameter_sets", ["run_id"])

    op.create_table("optimization_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("optimization_runs.id"), nullable=False),
        sa.Column("params_json", sa.String(2000), nullable=False),
        sa.Column("metrics_json", sa.String(5000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ores_run", "optimization_results", ["run_id"])

    op.create_table("walk_forward_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("window_count", sa.Integer(), server_default="0"),
        sa.Column("in_sample_months", sa.Integer(), server_default="6"),
        sa.Column("out_sample_months", sa.Integer(), server_default="2"),
        sa.Column("stability_score", sa.Float(), server_default="0.0"),
        sa.Column("results_json", sa.String(10000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table("monte_carlo_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("iterations", sa.Integer(), server_default="1000"),
        sa.Column("mean_equity", sa.Float(), server_default="0.0"),
        sa.Column("equity_std", sa.Float(), server_default="0.0"),
        sa.Column("risk_of_ruin", sa.Float(), server_default="0.0"),
        sa.Column("confidence_95_low", sa.Float(), server_default="0.0"),
        sa.Column("confidence_95_high", sa.Float(), server_default="0.0"),
        sa.Column("results_json", sa.String(20000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("monte_carlo_runs")
    op.drop_table("walk_forward_runs")
    op.drop_table("optimization_results")
    op.drop_table("parameter_sets")
    op.drop_table("optimization_runs")
