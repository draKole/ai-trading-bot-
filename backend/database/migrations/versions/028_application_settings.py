"""Create application_settings table for persisted non-secret defaults.

Revision ID: 028_application_settings
Create Date: 2026-07-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "028_application_settings"
down_revision: Union[str, None] = "027_trading_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_settings",
        sa.Column("id", sa.Integer(), primary_key=True, default=1),
        sa.Column(
            "trading_mode", sa.String(20), nullable=False, server_default="PAPER",
        ),
        sa.Column(
            "data_provider", sa.String(30), nullable=False, server_default="yfinance",
        ),
        sa.Column(
            "default_risk_percent", sa.Float(), nullable=False, server_default="1.0",
        ),
        sa.Column(
            "min_risk_reward", sa.Float(), nullable=False, server_default="2.0",
        ),
        sa.Column(
            "max_contracts", sa.Integer(), nullable=False, server_default="10",
        ),
        sa.Column(
            "max_trades_per_day", sa.Integer(), nullable=False, server_default="10",
        ),
        sa.Column(
            "max_trades_per_session",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Seed the singleton row (id=1) with defaults
    op.execute(
        "INSERT INTO application_settings (id) VALUES (1) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("application_settings")
