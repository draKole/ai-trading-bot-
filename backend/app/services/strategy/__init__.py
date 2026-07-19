"""Strategy Engine — Market Bias + Trade Setup Generator.

Consumes Confluence Engine output to produce standardized Market Bias
and Trade Setup objects. Advisory only — no order execution.

Components:
    - build_market_bias: Aggregate all engine evidence into directional bias
    - generate_trade_setup: Produce entry zone, targets, stop reference
    - evaluate_strategy_rules: Configurable rule evaluation
    - StrategyService: Persistence and query layer
"""

from app.services.strategy.engine import (
    build_market_bias, generate_trade_setup, evaluate_strategy_rules,
    MarketBias, TradeSetup, StrategyRule, StrategyConfig,
    SetupStatus, SetupGrade, BiasDirection, ConfidenceLevel,
    MarketRegime, score_to_grade, score_to_confidence,
    DEFAULT_SCORING_WEIGHTS, _default_strategy_rules,
)
from app.services.strategy.service import StrategyService

__all__ = [
    "build_market_bias", "generate_trade_setup", "evaluate_strategy_rules",
    "MarketBias", "TradeSetup", "StrategyRule", "StrategyConfig",
    "SetupStatus", "SetupGrade", "BiasDirection", "ConfidenceLevel",
    "MarketRegime", "score_to_grade", "score_to_confidence",
    "DEFAULT_SCORING_WEIGHTS", "_default_strategy_rules",
    "StrategyService",
]
