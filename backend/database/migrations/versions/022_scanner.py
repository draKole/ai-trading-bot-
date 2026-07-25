"""Add scanner tables. Revision 022."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "022_scanner"
down_revision: Union[str, None] = "021_optimization"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("watchlists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("name"),
    )
    op.create_table("watchlist_symbols",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframes", sa.String(100), server_default="5m"),
        sa.Column("is_enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    ); op.create_index("ix_ws_wl", "watchlist_symbols", ["watchlist_id"])

    op.create_table("scan_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("symbols_scanned", sa.Integer(), server_default="0"),
        sa.Column("opportunities_found", sa.Integer(), server_default="0"),
        sa.Column("duration_ms", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    ); op.create_index("ix_sr_wl", "scan_runs", ["watchlist_id"]); op.create_index("ix_sr_status", "scan_runs", ["status"])

    op.create_table("scan_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scan_runs.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("confidence", sa.String(20), server_default="Low"),
        sa.Column("detail_json", sa.String(2000), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    ); op.create_index("ix_sres_scan", "scan_results", ["scan_id"])

    op.create_table("opportunities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("scan_runs.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), server_default="neutral"),
        sa.Column("score", sa.Float(), server_default="0.0"),
        sa.Column("rank", sa.Integer(), server_default="0"),
        sa.Column("expected_reward", sa.Float(), server_default="0.0"),
        sa.Column("risk", sa.Float(), server_default="0.0"),
        sa.Column("metrics_json", sa.String(3000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    ); op.create_index("ix_opp_scan", "opportunities", ["scan_id"])


def downgrade() -> None:
    for t in ["opportunities", "scan_results", "scan_runs", "watchlist_symbols", "watchlists"]:
        op.drop_table(t)
