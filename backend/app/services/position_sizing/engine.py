"""Position Sizing Engine — determines appropriate position size.

Consumes Trade Setup + Risk Report + Account Config to produce
Position Size Recommendations. Advisory only — no execution.

Supports configurable risk models: Fixed Dollar, Fixed %,
Kelly Criterion, Fixed Contracts, Volatility-Based.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


# ─── Enums ──────────────────────────────────────────────────

class SizingMethod(str, Enum):
    FIXED_DOLLAR = "fixed_dollar"
    FIXED_PERCENTAGE = "fixed_percentage"
    KELLY = "kelly"
    FIXED_CONTRACTS = "fixed_contracts"
    VOLATILITY_BASED = "volatility_based"


class ConstraintStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


# ─── Account Config ─────────────────────────────────────────

@dataclass
class AccountConfig:
    """Configurable account parameters for position sizing."""

    # Account
    account_balance: float = 100000.0
    buying_power: float | None = None  # defaults to 2× balance for margin
    account_type: str = "margin"  # margin, cash, futures
    currency: str = "USD"

    # Risk limits
    max_risk_per_trade_pct: float = 1.0  # 1% of balance
    max_daily_loss_pct: float = 3.0      # 3% of balance
    max_daily_loss_dollar: float | None = None  # overrides pct if set
    max_open_positions: int = 5
    max_exposure_pct: float = 500.0  # max notional exposure as % of balance

    # Instrument specs (futures)
    tick_value: float = 12.50  # e.g., ES = $12.50 per tick
    tick_size: float = 0.25     # e.g., ES = 0.25 points
    contract_multiplier: float = 50.0  # e.g., ES = $50 per point
    margin_per_contract: float = 12000.0  # initial margin

    # Sizing method
    sizing_method: str = "fixed_percentage"
    fixed_dollar_risk: float = 500.0     # used by fixed_dollar
    fixed_contract_count: int = 1         # used by fixed_contracts
    kelly_fraction: float = 0.25          # Kelly fraction (conservative)
    volatility_atr: float = 0.0           # ATR for volatility-based

    def __post_init__(self):
        if self.buying_power is None:
            self.buying_power = self.account_balance * 2.0

    def to_dict(self) -> dict:
        return {
            "account_balance": self.account_balance,
            "buying_power": self.buying_power,
            "account_type": self.account_type,
            "currency": self.currency,
            "max_risk_per_trade_pct": self.max_risk_per_trade_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_daily_loss_dollar": self.max_daily_loss_dollar,
            "max_open_positions": self.max_open_positions,
            "max_exposure_pct": self.max_exposure_pct,
            "tick_value": self.tick_value,
            "tick_size": self.tick_size,
            "contract_multiplier": self.contract_multiplier,
            "margin_per_contract": self.margin_per_contract,
            "sizing_method": self.sizing_method,
            "fixed_dollar_risk": self.fixed_dollar_risk,
            "fixed_contract_count": self.fixed_contract_count,
            "kelly_fraction": self.kelly_fraction,
            "volatility_atr": self.volatility_atr,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AccountConfig:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


# ─── Risk Model Calculations ────────────────────────────────

def _calc_point_value(config: AccountConfig) -> float:
    """Dollar value per point of price movement."""
    if config.tick_size > 0:
        return config.tick_value / config.tick_size
    return config.contract_multiplier


def calc_dollar_risk(
    stop_distance_pts: float,
    config: AccountConfig,
) -> float:
    """Dollar risk for 1 contract at given stop distance."""
    point_value = _calc_point_value(config)
    return stop_distance_pts * point_value


def calc_max_contracts_by_risk(
    dollar_risk_per_trade: float,
    dollar_risk_per_contract: float,
) -> int:
    """Max contracts given dollar risk budget."""
    if dollar_risk_per_contract <= 0:
        return 0
    return int(dollar_risk_per_trade / dollar_risk_per_contract)


def calc_fixed_dollar_contracts(
    stop_distance_pts: float,
    config: AccountConfig,
) -> int:
    """Fixed dollar risk sizing."""
    risk_per_contract = calc_dollar_risk(stop_distance_pts, config)
    if risk_per_contract <= 0:
        return 0
    return int(config.fixed_dollar_risk / risk_per_contract)


def calc_fixed_pct_contracts(
    stop_distance_pts: float,
    config: AccountConfig,
) -> int:
    """Fixed percentage of account risk sizing."""
    dollar_risk = config.account_balance * (config.max_risk_per_trade_pct / 100)
    risk_per_contract = calc_dollar_risk(stop_distance_pts, config)
    if risk_per_contract <= 0:
        return 0
    return int(dollar_risk / risk_per_contract)


def calc_kelly_contracts(
    stop_distance_pts: float,
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    config: AccountConfig,
) -> int:
    """Kelly Criterion sizing (fractional).

    f* = (p * b - q) / b
    where p = win_rate, q = 1-p, b = avg_win/avg_loss
    """
    if avg_loss_pct <= 0 or stop_distance_pts <= 0:
        return 0

    p = win_rate
    q = 1 - p
    b = avg_win_pct / max(avg_loss_pct, 0.01)

    kelly_pct = max(0.0, (p * b - q) / max(b, 0.01))
    kelly_pct = kelly_pct * config.kelly_fraction

    dollar_risk = config.account_balance * kelly_pct
    risk_per_contract = calc_dollar_risk(stop_distance_pts, config)
    if risk_per_contract <= 0:
        return 0
    return max(0, int(dollar_risk / risk_per_contract))


def calc_fixed_contract_count(config: AccountConfig) -> int:
    """Fixed contract sizing."""
    return config.fixed_contract_count


# ─── Constraint Validation ──────────────────────────────────

@dataclass
class ConstraintResult:
    rule: str
    status: str
    detail: str = ""
    limit: float | None = None
    actual: float | None = None


def validate_constraints(
    contracts: int,
    stop_distance_pts: float,
    entry_price: float,
    config: AccountConfig,
    open_positions: int = 0,
    daily_loss_so_far: float = 0.0,
) -> list[ConstraintResult]:
    """Validate position size against all account limits."""
    results: list[ConstraintResult] = []

    if contracts <= 0:
        results.append(ConstraintResult("contracts_positive", "FAIL",
            "Contracts must be > 0", limit=1, actual=contracts))
        return results

    point_value = _calc_point_value(config)

    # Per-trade risk
    dollar_risk_per_contract = stop_distance_pts * point_value
    total_trade_risk = dollar_risk_per_contract * contracts
    max_trade_risk = config.account_balance * (config.max_risk_per_trade_pct / 100)

    if total_trade_risk <= max_trade_risk:
        results.append(ConstraintResult("max_trade_risk", "PASS",
            f"${total_trade_risk:.0f} ≤ ${max_trade_risk:.0f}",
            limit=max_trade_risk, actual=total_trade_risk))
    else:
        results.append(ConstraintResult("max_trade_risk", "FAIL",
            f"${total_trade_risk:.0f} > ${max_trade_risk:.0f}",
            limit=max_trade_risk, actual=total_trade_risk))

    # Daily loss
    daily_limit = config.max_daily_loss_dollar or (
        config.account_balance * (config.max_daily_loss_pct / 100))
    potential_daily = daily_loss_so_far + total_trade_risk
    if potential_daily <= daily_limit:
        results.append(ConstraintResult("max_daily_loss", "PASS",
            f"${potential_daily:.0f} ≤ ${daily_limit:.0f}",
            limit=daily_limit, actual=potential_daily))
    else:
        results.append(ConstraintResult("max_daily_loss", "FAIL",
            f"${potential_daily:.0f} > ${daily_limit:.0f}",
            limit=daily_limit, actual=potential_daily))

    # Max contracts (instrument limit: sensible default)
    max_contracts = 100  # could be instrument-specific
    if contracts <= max_contracts:
        results.append(ConstraintResult("max_contracts", "PASS",
            f"{contracts} ≤ {max_contracts}", limit=max_contracts, actual=contracts))
    else:
        results.append(ConstraintResult("max_contracts", "FAIL",
            f"{contracts} > {max_contracts}", limit=max_contracts, actual=contracts))

    # Margin
    margin_required = config.margin_per_contract * contracts
    if margin_required <= config.buying_power:
        results.append(ConstraintResult("margin", "PASS",
            f"${margin_required:.0f} ≤ ${config.buying_power:.0f}",
            limit=config.buying_power, actual=margin_required))
    else:
        results.append(ConstraintResult("margin", "FAIL",
            f"${margin_required:.0f} > ${config.buying_power:.0f}",
            limit=config.buying_power, actual=margin_required))

    # Open positions
    if open_positions < config.max_open_positions:
        results.append(ConstraintResult("open_positions", "PASS",
            f"{open_positions} < {config.max_open_positions}",
            limit=config.max_open_positions, actual=open_positions))
    else:
        results.append(ConstraintResult("open_positions", "FAIL",
            f"{open_positions} ≥ {config.max_open_positions}",
            limit=config.max_open_positions, actual=open_positions))

    # Exposure
    notional = contracts * entry_price * config.contract_multiplier
    max_exposure = config.account_balance * (config.max_exposure_pct / 100)
    if notional <= max_exposure:
        results.append(ConstraintResult("exposure", "PASS",
            f"${notional:.0f} ≤ ${max_exposure:.0f}",
            limit=max_exposure, actual=notional))
    else:
        results.append(ConstraintResult("exposure", "FAIL",
            f"${notional:.0f} > ${max_exposure:.0f}",
            limit=max_exposure, actual=notional))

    return results


# ─── Position Recommendation ────────────────────────────────

@dataclass
class PositionRecommendation:
    """Advisory position size recommendation."""

    recommendation_id: str = field(default_factory=lambda: str(uuid4()))
    setup_id: str = ""
    instrument: str = ""
    direction: str = ""
    sizing_method: str = ""

    # Quantities
    recommended_contracts: int = 0
    conservative_contracts: int = 0
    max_allowable_contracts: int = 0

    # Dollar values
    dollar_risk_per_contract: float = 0.0
    total_dollar_risk: float = 0.0
    margin_required: float = 0.0
    capital_utilization_pct: float = 0.0
    effective_leverage: float = 0.0

    # Risk percentage
    risk_pct_of_account: float = 0.0

    # Constraints
    constraint_results: list[dict] = field(default_factory=list)
    all_constraints_pass: bool = False
    failure_reasons: list[str] = field(default_factory=list)

    # Metadata
    config_snapshot: dict = field(default_factory=dict)
    generated_timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "recommendation_id": self.recommendation_id,
            "setup_id": self.setup_id,
            "instrument": self.instrument,
            "direction": self.direction,
            "sizing_method": self.sizing_method,
            "recommended_contracts": self.recommended_contracts,
            "conservative_contracts": self.conservative_contracts,
            "max_allowable_contracts": self.max_allowable_contracts,
            "dollar_risk_per_contract": round(self.dollar_risk_per_contract, 2),
            "total_dollar_risk": round(self.total_dollar_risk, 2),
            "margin_required": round(self.margin_required, 2),
            "capital_utilization_pct": round(self.capital_utilization_pct, 2),
            "effective_leverage": round(self.effective_leverage, 2),
            "risk_pct_of_account": round(self.risk_pct_of_account, 4),
            "constraint_results": self.constraint_results,
            "all_constraints_pass": self.all_constraints_pass,
            "failure_reasons": self.failure_reasons,
        }


# ─── Main Entry Point ───────────────────────────────────────

def calculate_position(
    setup: dict,
    risk_report: dict | None = None,
    config: AccountConfig | None = None,
    open_positions: int = 0,
    daily_loss_so_far: float = 0.0,
) -> PositionRecommendation:
    """Calculate position size recommendation.

    Args:
        setup: Trade setup dict with instrument, direction, preferred_entry,
               stop_reference, entry_zone_low, entry_zone_high.
        risk_report: Risk report dict with stop_distance_points.
        config: Account configuration.
        open_positions: Current open position count.
        daily_loss_so_far: Loss accumulated today.

    Returns:
        PositionRecommendation with contract quantities and constraints.
    """
    if config is None:
        config = AccountConfig()

    instrument = str(setup.get("instrument", ""))
    direction = str(setup.get("direction", ""))
    entry = float(setup.get("preferred_entry", 0) or
                  ((setup.get("entry_zone_low", 0) or 0) +
                   (setup.get("entry_zone_high", 0) or 0)) / 2)

    stop = float(setup.get("stop_reference", 0) or 0)

    # Stop distance in points
    if entry > 0 and stop > 0:
        if direction == "bullish":
            stop_distance_pts = entry - stop
        else:
            stop_distance_pts = stop - entry
    else:
        # Fallback: use risk report
        stop_distance_pts = float(
            (risk_report or {}).get("assessment", {}).get("stop_distance_points", 0) or 0
        )

    if stop_distance_pts <= 0:
        stop_distance_pts = 1.0  # sensible minimum for calc

    # Calculate contracts by method
    method = config.sizing_method

    if method == "fixed_dollar":
        recommended = calc_fixed_dollar_contracts(stop_distance_pts, config)
    elif method == "fixed_contracts":
        recommended = calc_fixed_contract_count(config)
    elif method == "kelly":
        recommended = calc_kelly_contracts(
            stop_distance_pts, win_rate=0.5,
            avg_win_pct=2.0, avg_loss_pct=1.0, config=config,
        )
    elif method == "volatility_based":
        # Placeholder: use ATR to adjust stop distance
        atr = config.volatility_atr if config.volatility_atr > 0 else stop_distance_pts
        recommended = calc_fixed_pct_contracts(atr, config) if atr > 0 else 0
    else:
        # fixed_percentage (default)
        recommended = calc_fixed_pct_contracts(stop_distance_pts, config)

    recommended = max(0, recommended)

    # Conservative = floor(recommended * 0.5)
    conservative = max(0, int(recommended * 0.5))

    # Max allowable = what the constraints allow
    max_by_risk = calc_max_contracts_by_risk(
        config.account_balance * (config.max_risk_per_trade_pct / 100),
        calc_dollar_risk(stop_distance_pts, config),
    )
    max_by_margin = int(config.buying_power / max(config.margin_per_contract, 1))
    max_allowable = min(max_by_risk, max_by_margin, 100)
    max_allowable = max(1, max_allowable)  # at least 1 contract

    # Dollar calculations
    point_value = _calc_point_value(config)
    dollar_risk_per_contract = stop_distance_pts * point_value
    total_dollar_risk = dollar_risk_per_contract * recommended
    margin_required = config.margin_per_contract * recommended
    capital_utilization_pct = (margin_required / config.account_balance * 100) if config.account_balance > 0 else 0
    risk_pct = (total_dollar_risk / config.account_balance * 100) if config.account_balance > 0 else 0

    # Effective leverage
    notional = recommended * entry * config.contract_multiplier if entry > 0 else 0
    effective_leverage = (notional / config.account_balance) if config.account_balance > 0 else 0

    # Validate constraints
    constraint_results = validate_constraints(
        recommended, stop_distance_pts, entry, config,
        open_positions, daily_loss_so_far,
    )

    all_pass = all(r.status == "PASS" for r in constraint_results)
    failures = [r.detail for r in constraint_results if r.status == "FAIL"]

    return PositionRecommendation(
        setup_id=str(setup.get("setup_id", "")),
        instrument=instrument,
        direction=direction,
        sizing_method=method,
        recommended_contracts=recommended,
        conservative_contracts=conservative,
        max_allowable_contracts=max_allowable,
        dollar_risk_per_contract=dollar_risk_per_contract,
        total_dollar_risk=total_dollar_risk,
        margin_required=margin_required,
        capital_utilization_pct=round(capital_utilization_pct, 2),
        effective_leverage=round(effective_leverage, 2),
        risk_pct_of_account=round(risk_pct, 4),
        constraint_results=[
            {"rule": r.rule, "status": r.status, "detail": r.detail,
             "limit": r.limit, "actual": r.actual}
            for r in constraint_results
        ],
        all_constraints_pass=all_pass,
        failure_reasons=failures,
        config_snapshot=config.to_dict(),
    )
