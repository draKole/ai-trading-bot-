"""Add position sizing tables: position_recommendations, position_sizing_rules, position_sizing_evaluations.

Revision ID: 010
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "010_position_sizing"
down_revision: Union[str, None] = "009_risk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "position_recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recommendation_id", sa.String(36), nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(15), nullable=False),
        sa.Column("sizing_method", sa.String(30), server_default="fixed_percentage"),
        sa.Column("recommended_contracts", sa.Integer(), server_default="0"),
        sa.Column("conservative_contracts", sa.Integer(), server_default="0"),
        sa.Column("max_allowable_contracts", sa.Integer(), server_default="0"),
        sa.Column("dollar_risk_per_contract", sa.Float(), server_default="0.0"),
        sa.Column("total_dollar_risk", sa.Float(), server_default="0.0"),
        sa.Column("margin_required", sa.Float(), server_default="0.0"),
        sa.Column("capital_utilization_pct", sa.Float(), server_default="0.0"),
        sa.Column("effective_leverage", sa.Float(), server_default="0.0"),
        sa.Column("risk_pct_of_account", sa.Float(), server_default="0.0"),
        sa.Column("constraint_results_json", sa.JSON(), nullable=True),
        sa.Column("all_constraints_pass", sa.Boolean(), server_default="false"),
        sa.Column("failure_reasons_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_id"),
    )
    op.create_index("ix_pr_rec_id", "position_recommendations", ["recommendation_id"])
    op.create_index("ix_pr_setup", "position_recommendations", ["setup_id"])
    op.create_index("ix_pr_instrument", "position_recommendations", ["instrument"])

    op.create_table(
        "position_sizing_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), server_default=""),
        sa.Column("rule_type", sa.String(30), server_default="limit"),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("group", sa.String(50), server_default="default"),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "position_sizing_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recommendation_id", sa.String(36), nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(10), server_default="FAIL"),
        sa.Column("detail", sa.String(500), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pse_rec", "position_sizing_evaluations", ["recommendation_id"])
    op.create_index("ix_pse_setup", "position_sizing_evaluations", ["setup_id"])
    op.create_index("ix_pse_rule", "position_sizing_evaluations", ["rule_name"])


def downgrade() -> None:
    op.drop_table("position_sizing_evaluations")
    op.drop_table("position_sizing_rules")
    op.drop_table("position_recommendations")
