"""Add strategy tables: market_biases, trade_setups, strategy_rules, strategy_evaluations.

Revision ID: 008
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "008_strategy"
down_revision: Union[str, None] = "007_confluence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_biases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=True),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(15), server_default="neutral"),
        sa.Column("strength_score", sa.Float(), server_default="0.0"),
        sa.Column("confidence", sa.String(20), server_default="Very Low"),
        sa.Column("trend", sa.String(15), server_default="neutral"),
        sa.Column("market_regime", sa.String(15), server_default="ranging"),
        sa.Column("session", sa.String(20), server_default="unknown"),
        sa.Column("bias_grade", sa.String(3), server_default="F"),
        sa.Column("supporting_evidence_json", sa.JSON(), nullable=True),
        sa.Column("contradicting_evidence_json", sa.JSON(), nullable=True),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mb_setup", "market_biases", ["setup_id"])
    op.create_index("ix_mb_instrument", "market_biases", ["instrument"])
    op.create_index("ix_mb_timeframe", "market_biases", ["timeframe"])
    op.create_index("ix_mb_timestamp", "market_biases", ["timestamp"])

    op.create_table(
        "trade_setups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(15), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("entry_zone_low", sa.Float(), nullable=True),
        sa.Column("entry_zone_high", sa.Float(), nullable=True),
        sa.Column("preferred_entry", sa.Float(), nullable=True),
        sa.Column("stop_reference", sa.Float(), nullable=True),
        sa.Column("target_1", sa.Float(), nullable=True),
        sa.Column("target_2", sa.Float(), nullable=True),
        sa.Column("target_3", sa.Float(), nullable=True),
        sa.Column("required_confirmation_json", sa.JSON(), nullable=True),
        sa.Column("bias_id", sa.Integer(), nullable=True),
        sa.Column("supporting_evidence_json", sa.JSON(), nullable=True),
        sa.Column("contradictions_json", sa.JSON(), nullable=True),
        sa.Column("setup_score", sa.Float(), server_default="0.0"),
        sa.Column("setup_grade", sa.String(3), server_default="F"),
        sa.Column("strategy_version", sa.String(20), server_default="1.0.0"),
        sa.Column("generated_timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setup_id"),
    )
    op.create_index("ix_ts_setup_id", "trade_setups", ["setup_id"])
    op.create_index("ix_ts_instrument", "trade_setups", ["instrument"])
    op.create_index("ix_ts_timeframe", "trade_setups", ["timeframe"])
    op.create_index("ix_ts_status", "trade_setups", ["status"])

    op.create_table(
        "strategy_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("direction", sa.String(15), server_default="neutral"),
        sa.Column("required_conditions_json", sa.JSON(), nullable=False),
        sa.Column("optional_conditions_json", sa.JSON(), nullable=False),
        sa.Column("min_score", sa.Float(), server_default="60.0"),
        sa.Column("group", sa.String(50), server_default="default"),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("weight", sa.Float(), server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "strategy_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("passed", sa.Boolean(), server_default="false"),
        sa.Column("direction", sa.String(15), server_default="neutral"),
        sa.Column("required_met", sa.Integer(), server_default="0"),
        sa.Column("required_total", sa.Integer(), server_default="0"),
        sa.Column("optional_met", sa.Integer(), server_default="0"),
        sa.Column("optional_total", sa.Integer(), server_default="0"),
        sa.Column("min_score", sa.Float(), server_default="0.0"),
        sa.Column("setup_score", sa.Float(), server_default="0.0"),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("group", sa.String(50), server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_se_setup", "strategy_evaluations", ["setup_id"])
    op.create_index("ix_se_rule", "strategy_evaluations", ["rule_name"])


def downgrade() -> None:
    op.drop_table("strategy_evaluations")
    op.drop_table("strategy_rules")
    op.drop_table("trade_setups")
    op.drop_table("market_biases")
