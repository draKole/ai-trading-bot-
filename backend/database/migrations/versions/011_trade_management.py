"""Add trade management tables: managed_trades, trade_events, trade_management_rules.

Revision ID: 011
Create Date: 2026-07-16
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "011_trade_management"
down_revision: Union[str, None] = "010_position_sizing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "managed_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trade_id", sa.String(36), nullable=False),
        sa.Column("setup_id", sa.String(36), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(15), nullable=False),
        sa.Column("entry_price", sa.Float(), server_default="0.0"),
        sa.Column("initial_stop", sa.Float(), server_default="0.0"),
        sa.Column("current_stop", sa.Float(), server_default="0.0"),
        sa.Column("position_size", sa.Integer(), server_default="0"),
        sa.Column("position_remaining", sa.Integer(), server_default="0"),
        sa.Column("target_1", sa.Float(), nullable=True),
        sa.Column("target_2", sa.Float(), nullable=True),
        sa.Column("target_3", sa.Float(), nullable=True),
        sa.Column("target_1_hit", sa.Boolean(), server_default="false"),
        sa.Column("target_2_hit", sa.Boolean(), server_default="false"),
        sa.Column("target_3_hit", sa.Boolean(), server_default="false"),
        sa.Column("state", sa.String(30), server_default="pending_entry"),
        sa.Column("initial_risk_r", sa.Float(), server_default="0.0"),
        sa.Column("peak_r", sa.Float(), server_default="0.0"),
        sa.Column("max_adverse_r", sa.Float(), server_default="0.0"),
        sa.Column("current_r", sa.Float(), server_default="0.0"),
        sa.Column("breakeven_reached", sa.Boolean(), server_default="false"),
        sa.Column("trailing_active", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_id"),
    )
    op.create_index("ix_mt_trade", "managed_trades", ["trade_id"])
    op.create_index("ix_mt_setup", "managed_trades", ["setup_id"])
    op.create_index("ix_mt_instrument", "managed_trades", ["instrument"])
    op.create_index("ix_mt_state", "managed_trades", ["state"])

    op.create_table(
        "trade_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trade_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("from_state", sa.String(30), server_default=""),
        sa.Column("to_state", sa.String(30), server_default=""),
        sa.Column("detail", sa.String(500), server_default=""),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("r_multiple", sa.Float(), server_default="0.0"),
        sa.Column("position_remaining_pct", sa.Float(), server_default="100.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_te_trade", "trade_events", ["trade_id"])

    op.create_table(
        "trade_management_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), server_default=""),
        sa.Column("rule_type", sa.String(30), server_default="threshold"),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("group", sa.String(50), server_default="default"),
        sa.Column("priority", sa.Integer(), server_default="0"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("trade_management_rules")
    op.drop_table("trade_events")
    op.drop_table("managed_trades")
