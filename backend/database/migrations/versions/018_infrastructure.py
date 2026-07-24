"""Infrastructure migration — Alembic 018, depends on 017_monitoring."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "018_infrastructure"
down_revision: Union[str, None] = "017_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Infrastructure migration — no schema changes required."""
    pass


def downgrade() -> None:
    """Infrastructure migration — no schema changes required."""
    pass
