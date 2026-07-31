"""Create trading_audit_logs table for immutable order/fill/cancel audit trail.

Revision ID: 027_trading_audit_logs
Create Date: 2026-07-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "027_trading_audit_logs"
down_revision: Union[str, None] = "026_seed_es_nq_mnq_instruments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("client_order_id", sa.String(64), nullable=True),
        sa.Column("broker_order_id", sa.String(64), nullable=True),
        sa.Column("instrument", sa.String(20), nullable=True),
        sa.Column("side", sa.String(10), nullable=True),
        sa.Column("order_type", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("fill_price", sa.Float(), nullable=True),
        sa.Column("commission", sa.Float(), nullable=True),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("mode", sa.String(10), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tal_event_type", "trading_audit_logs", ["event_type"])
    op.create_index("ix_tal_client_order_id", "trading_audit_logs", ["client_order_id"])
    op.create_index("ix_tal_mode", "trading_audit_logs", ["mode"])
    op.create_index("ix_tal_created_at", "trading_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tal_created_at", table_name="trading_audit_logs")
    op.drop_index("ix_tal_mode", table_name="trading_audit_logs")
    op.drop_index("ix_tal_client_order_id", table_name="trading_audit_logs")
    op.drop_index("ix_tal_event_type", table_name="trading_audit_logs")
    op.drop_table("trading_audit_logs")
