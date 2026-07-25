"""Add dashboard tables. Revision 023."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "023_dashboard"
down_revision: Union[str, None] = "022_scanner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("dashboard_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_type", sa.String(50), nullable=False, server_default="full"),
        sa.Column("data_json", sa.String(10000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ds_type", "dashboard_snapshots", ["snapshot_type"])

    op.create_table("dashboard_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, server_default="0"),
        sa.Column("preference_key", sa.String(100), nullable=False),
        sa.Column("preference_value", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dp_user", "dashboard_preferences", ["user_id"])

    op.create_table("dashboard_layouts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, server_default="0"),
        sa.Column("layout_name", sa.String(100), nullable=False, server_default="default"),
        sa.Column("widgets_json", sa.String(5000), nullable=True),
        sa.Column("is_active", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dl_user", "dashboard_layouts", ["user_id"])


def downgrade() -> None:
    for t in ["dashboard_layouts", "dashboard_preferences", "dashboard_snapshots"]:
        op.drop_table(t)
