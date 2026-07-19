"""Confluence Engine — unified market state from all analysis layers.

Combines Market Structure, Liquidity, FVG, Order Block, and SMT
outputs into ConfluenceSnapshots with configurable rule evaluation.

Components:
    - build_snapshot: Aggregate all engine outputs
    - evaluate_rules: Evaluate conditions without making trade decisions
    - ConfluenceService: Persistence and query layer
"""

from app.services.confluence.engine import (
    build_snapshot, evaluate_rules,
    ConfluenceConfig, ConfluenceSnapshot,
    Rule, RuleCondition, RuleResult,
    ConditionOperator, TrendState, SignalDirection,
)
from app.services.confluence.service import ConfluenceService

__all__ = [
    "build_snapshot", "evaluate_rules",
    "ConfluenceConfig", "ConfluenceSnapshot",
    "Rule", "RuleCondition", "RuleResult",
    "ConditionOperator", "TrendState", "SignalDirection",
    "ConfluenceService",
]
