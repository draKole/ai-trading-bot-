"""Add monitoring tables: system_health, alerts, audit_logs, performance_metrics.

Revision ID: 017
Create Date: 2026-07-24
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "017_monitoring"
down_revision: Union[str, None] = "016_live_broker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_health",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("component", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="unknown"),
        sa.Column("detail", sa.String(500), server_default=""),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sh_component", "system_health", ["component"])
    op.create_index("ix_sh_timestamp", "system_health", ["timestamp"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), server_default="warning"),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_created", "alerts", ["created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), server_default=""),
        sa.Column("entity_id", sa.String(100), server_default=""),
        sa.Column("detail_json", sa.String(2000), server_default="{}"),
        sa.Column("operator", sa.String(50), server_default="system"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_timestamp", "audit_logs", ["timestamp"])

    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("tags_json", sa.String(500), server_default="{}"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pm_name", "performance_metrics", ["name"])
    op.create_index("ix_pm_timestamp", "performance_metrics", ["timestamp"])


def downgrade() -> None:
    op.drop_table("performance_metrics")
    op.drop_table("audit_logs")
    op.drop_table("alerts")
    op.drop_table("system_health")
