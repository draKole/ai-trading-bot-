"""Risk Engine — evaluates Trade Setups against configurable risk criteria.

Consumes Trade Setup + Market Bias to produce Risk Reports with
validation, classification, and detailed scoring.

Components:
    - compute_assessment: Numerical risk metrics (R:R, stop %, volatility)
    - validate_setup: Configurable validation rules
    - evaluate_risk: Full pipeline → RiskReport
    - RiskService: Persistence and query layer
"""

from app.services.risk.engine import (
    compute_assessment, validate_setup, evaluate_risk,
    RiskAssessment, ValidationItem, ValidationSummary,
    RiskReport, RiskConfig, RiskClassification, ValidationResult,
    compute_risk_score, classify_risk,
)
from app.services.risk.service import RiskService

__all__ = [
    "compute_assessment", "validate_setup", "evaluate_risk",
    "RiskAssessment", "ValidationItem", "ValidationSummary",
    "RiskReport", "RiskConfig", "RiskClassification", "ValidationResult",
    "compute_risk_score", "classify_risk",
    "RiskService",
]
