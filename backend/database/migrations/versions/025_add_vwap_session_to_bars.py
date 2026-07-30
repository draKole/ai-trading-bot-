"""Add vwap and session columns to bars table.

Revision ID: 025
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "025_add_vwap_session_to_bars"
down_revision: Union[str, None] = "024_copilot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bars",
        sa.Column("vwap", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "bars",
        sa.Column("session", sa.String(20), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("bars", "session")
    op.drop_column("bars", "vwap")
