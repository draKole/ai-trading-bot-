"""Add risk tables: risk_reports, risk_rules, risk_evaluations.

Revision ID: 009
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "009_risk"
down_revision: Union[str, None] = "008_strategy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(15), nullable=False),
        sa.Column("overall_risk_score", sa.Float(), server_default="0.0"),
        sa.Column("risk_classification", sa.String(15), server_default="Extreme"),
        sa.Column("reward_risk_ratio", sa.Float(), server_default="0.0"),
        sa.Column("stop_distance_pct", sa.Float(), server_default="0.0"),
        sa.Column("mfe_estimate", sa.Float(), server_default="0.0"),
        sa.Column("expected_value", sa.Float(), server_default="0.0"),
        sa.Column("volatility_pct", sa.Float(), server_default="0.0"),
        sa.Column("setup_stability_score", sa.Float(), server_default="0.0"),
        sa.Column("validation_json", sa.JSON(), nullable=True),
        sa.Column("supporting_evidence_json", sa.JSON(), nullable=True),
        sa.Column("contradicting_evidence_json", sa.JSON(), nullable=True),
        sa.Column("failure_reasons_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rr_setup", "risk_reports", ["setup_id"])
    op.create_index("ix_rr_instrument", "risk_reports", ["instrument"])
    op.create_index("ix_rr_timeframe", "risk_reports", ["timeframe"])
    op.create_index("ix_rr_class", "risk_reports", ["risk_classification"])

    op.create_table(
        "risk_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), server_default=""),
        sa.Column("rule_type", sa.String(30), server_default="threshold"),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("warn_threshold", sa.Float(), nullable=True),
        sa.Column("operator", sa.String(10), server_default="gte"),
        sa.Column("field", sa.String(50), server_default=""),
        sa.Column("group", sa.String(50), server_default="default"),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "risk_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("result", sa.String(10), server_default="FAIL"),
        sa.Column("detail", sa.String(500), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_re_report", "risk_evaluations", ["report_id"])
    op.create_index("ix_re_setup", "risk_evaluations", ["setup_id"])
    op.create_index("ix_re_rule", "risk_evaluations", ["rule_name"])


def downgrade() -> None:
    op.drop_table("risk_evaluations")
    op.drop_table("risk_rules")
    op.drop_table("risk_reports")
