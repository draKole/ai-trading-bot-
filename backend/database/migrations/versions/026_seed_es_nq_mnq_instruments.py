"""Ensure ES, NQ, MNQ instruments are seeded with correct specifications.

Revision ID: 026
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op


revision: str = "026_seed_es_nq_mnq_instruments"
down_revision: Union[str, None] = "025_add_vwap_session_to_bars"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upsert ES, NQ, MNQ instruments with correct specifications."""
    op.execute("""
        INSERT INTO instruments (symbol, name, exchange, tick_size, tick_value, multiplier)
        VALUES
            ('ES',  'E-mini S&P 500',           'CME', 0.25, 12.50, 50),
            ('NQ',  'E-mini Nasdaq-100',        'CME', 0.25, 5.00,  20),
            ('MNQ', 'Micro E-mini Nasdaq-100',  'CME', 0.25, 0.50,  2)
        ON CONFLICT (symbol) DO UPDATE SET
            name = EXCLUDED.name,
            tick_size = EXCLUDED.tick_size,
            tick_value = EXCLUDED.tick_value,
            multiplier = EXCLUDED.multiplier
    """)


def downgrade() -> None:
    """No destructive downgrade — instruments may be in use."""
    pass
