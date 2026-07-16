"""Initial schema — instruments and bars hypertable.

Revision ID: 001
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Instruments ─────────────────────────────────────────
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("exchange", sa.String(20), nullable=False, server_default="CME"),
        sa.Column("tick_size", sa.Float(), nullable=False),
        sa.Column("tick_value", sa.Float(), nullable=False),
        sa.Column("multiplier", sa.Integer(), nullable=False),
        sa.Column("min_contracts", sa.Integer(), server_default="1"),
        sa.Column("max_contracts", sa.Integer(), server_default="10"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])

    # ─── Bars (Hypertable) ───────────────────────────────────
    op.create_table(
        "bars",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id", "timeframe", "timestamp", "provider",
            name="uq_bar_instrument_tf_ts_provider",
        ),
    )
    op.create_index("ix_bars_instrument_id", "bars", ["instrument_id"])
    op.create_index("ix_bars_timeframe", "bars", ["timeframe"])
    op.create_index("ix_bars_timestamp", "bars", ["timestamp"])
    op.create_index(
        "ix_bars_lookup",
        "bars",
        ["instrument_id", "timeframe", "timestamp"],
    )

    # Convert to TimescaleDB hypertable
    op.execute(
        "SELECT create_hypertable('bars', 'timestamp', "
        "chunk_time_interval => INTERVAL '7 days', "
        "if_not_exists => TRUE)"
    )

    # ─── Seed default instruments ────────────────────────────
    op.execute("""
        INSERT INTO instruments (symbol, name, exchange, tick_size, tick_value, multiplier)
        VALUES
            ('MNQ', 'Micro E-mini Nasdaq-100', 'CME', 0.25, 0.50, 2),
            ('NQ',  'E-mini Nasdaq-100',       'CME', 0.25, 5.00, 20),
            ('MES', 'Micro E-mini S&P 500',     'CME', 0.25, 1.25, 5),
            ('ES',  'E-mini S&P 500',           'CME', 0.25, 12.50, 50)
        ON CONFLICT (symbol) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("bars")
    op.drop_table("instruments")
