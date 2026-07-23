"""Position Sizing Engine — determines appropriate position size.

Consumes Trade Setup + Risk Report + Account Config to produce
Position Size Recommendations. Advisory only — no execution.

Components:
    - calculate_position: Full pipeline → PositionRecommendation
    - PositionSizingService: Persistence and query layer
"""

from app.services.position_sizing.engine import (
    calculate_position,
    PositionRecommendation, AccountConfig,
    SizingMethod, ConstraintStatus,
    calc_dollar_risk, calc_max_contracts_by_risk,
    calc_fixed_dollar_contracts, calc_fixed_pct_contracts,
    calc_kelly_contracts, calc_fixed_contract_count,
    validate_constraints, ConstraintResult,
)
from app.services.position_sizing.service import PositionSizingService

__all__ = [
    "calculate_position",
    "PositionRecommendation", "AccountConfig",
    "SizingMethod", "ConstraintStatus",
    "calc_dollar_risk", "calc_max_contracts_by_risk",
    "calc_fixed_dollar_contracts", "calc_fixed_pct_contracts",
    "calc_kelly_contracts", "calc_fixed_contract_count",
    "validate_constraints", "ConstraintResult",
    "PositionSizingService",
]
