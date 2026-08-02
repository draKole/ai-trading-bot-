"""Seed the MES instrument required by the market-data runtime contract.
Revision ID: 029
Create Date: 2026-08-02
"""
from typing import Sequence, Union
from alembic import op
revision: str = "029_seed_mes_instrument"
down_revision: Union[str, None] = "028_application_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    """Upsert Micro E-mini S&P 500 without changing existing instruments."""
    op.execute("""
        INSERT INTO instruments (symbol, name, exchange, tick_size, tick_value, multiplier)
        VALUES ('MES', 'Micro E-mini S&P 500', 'CME', 0.25, 1.25, 5)
        ON CONFLICT (symbol) DO UPDATE SET
            name = EXCLUDED.name,
            tick_size = EXCLUDED.tick_size,
            tick_value = EXCLUDED.tick_value,
            multiplier = EXCLUDED.multiplier
    """)
def downgrade() -> None:
    """Retain instruments because they may be in use."""
    pass
