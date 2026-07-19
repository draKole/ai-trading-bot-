"""Add confluence_snapshots, confluence_rule_results, confluence_rules tables.

Revision ID: 007
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "007_confluence"
down_revision: Union[str, None] = "006_smt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "confluence_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trend", sa.String(15), server_default="neutral"),
        sa.Column("trend_confidence", sa.Float(), server_default="0.0"),
        sa.Column("ms_event_count", sa.Integer(), server_default="0"),
        sa.Column("ms_bullish_count", sa.Integer(), server_default="0"),
        sa.Column("ms_bearish_count", sa.Integer(), server_default="0"),
        sa.Column("swing_direction", sa.String(15), server_default="neutral"),
        sa.Column("latest_bos_json", sa.JSON(), nullable=True),
        sa.Column("latest_choch_json", sa.JSON(), nullable=True),
        sa.Column("liquidity_level_count", sa.Integer(), server_default="0"),
        sa.Column("active_sweeps_count", sa.Integer(), server_default="0"),
        sa.Column("active_sweeps_bullish", sa.Integer(), server_default="0"),
        sa.Column("active_sweeps_bearish", sa.Integer(), server_default="0"),
        sa.Column("fvg_active_count", sa.Integer(), server_default="0"),
        sa.Column("fvg_bullish_count", sa.Integer(), server_default="0"),
        sa.Column("fvg_bearish_count", sa.Integer(), server_default="0"),
        sa.Column("fvg_mitigated_count", sa.Integer(), server_default="0"),
        sa.Column("ob_active_count", sa.Integer(), server_default="0"),
        sa.Column("ob_bullish_count", sa.Integer(), server_default="0"),
        sa.Column("ob_bearish_count", sa.Integer(), server_default="0"),
        sa.Column("ob_mitigated_count", sa.Integer(), server_default="0"),
        sa.Column("smt_active_count", sa.Integer(), server_default="0"),
        sa.Column("smt_bullish_count", sa.Integer(), server_default="0"),
        sa.Column("smt_bearish_count", sa.Integer(), server_default="0"),
        sa.Column("session", sa.String(20), server_default="unknown"),
        sa.Column("session_aligned", sa.Boolean(), server_default="false"),
        sa.Column("bullish_signals", sa.Float(), server_default="0.0"),
        sa.Column("bearish_signals", sa.Float(), server_default="0.0"),
        sa.Column("neutral_signals", sa.Integer(), server_default="0"),
        sa.Column("total_signals", sa.Float(), server_default="0.0"),
        sa.Column("agreement_ratio", sa.Float(), server_default="0.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cs_instrument", "confluence_snapshots", ["instrument"])
    op.create_index("ix_cs_timeframe", "confluence_snapshots", ["timeframe"])
    op.create_index("ix_cs_timestamp", "confluence_snapshots", ["timestamp"])
    op.create_index("ix_cs_lookup", "confluence_snapshots", ["instrument", "timeframe"])

    op.create_table(
        "confluence_rule_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("matched", sa.Boolean(), server_default="false"),
        sa.Column("direction", sa.String(15), server_default="neutral"),
        sa.Column("match_count", sa.Integer(), server_default="0"),
        sa.Column("total_conditions", sa.Integer(), server_default="0"),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("matched_conditions_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crr_snapshot", "confluence_rule_results", ["snapshot_id"])
    op.create_index("ix_crr_rule", "confluence_rule_results", ["rule_name"])

    op.create_table(
        "confluence_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), server_default=""),
        sa.Column("conditions_json", sa.JSON(), nullable=False),
        sa.Column("operator", sa.String(20), server_default="all"),
        sa.Column("min_matches", sa.Integer(), server_default="1"),
        sa.Column("group", sa.String(50), server_default="default"),
        sa.Column("weight", sa.Float(), server_default="1.0"),
        sa.Column("direction", sa.String(15), server_default="neutral"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("confluence_rules")
    op.drop_table("confluence_rule_results")
    op.drop_table("confluence_snapshots")
