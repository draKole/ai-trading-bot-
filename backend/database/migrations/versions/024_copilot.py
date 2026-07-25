"""Add copilot tables. Revision 024."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "024_copilot"
down_revision: Union[str, None] = "023_dashboard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("copilot_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("context_json", sa.String(5000), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cs_status", "copilot_sessions", ["status"])

    op.create_table("copilot_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("copilot_sessions.id"), nullable=False),
        sa.Column("title", sa.String(200), server_default="New Conversation"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cc_session", "copilot_conversations", ["session_id"])

    op.create_table("copilot_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("copilot_conversations.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.String(5000), nullable=False),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("source_services", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cm_conv", "copilot_messages", ["conversation_id"])

    op.create_table("copilot_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("copilot_messages.id"), nullable=False),
        sa.Column("rating", sa.Integer(), server_default="0"),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cf_msg", "copilot_feedback", ["message_id"])


def downgrade() -> None:
    for t in ["copilot_feedback", "copilot_messages", "copilot_conversations", "copilot_sessions"]:
        op.drop_table(t)
