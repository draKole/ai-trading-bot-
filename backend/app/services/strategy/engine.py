"""Strategy Engine — Market Bias + Trade Setup Generator.

Consumes Confluence snapshots and produces standardized Market Bias
and Trade Setup objects. Advisory only — no order execution.

Architecture:
    ConfluenceSnapshot → MarketBiasEngine → StrategyRuleEngine
                                                  ↓
                                           TradeSetupGenerator
                                                  ↓
                                            TradeSetup (advisory)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4


# ─── Enums ───────────────────────────────────────────────────

class BiasDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConfidenceLevel(str, Enum):
    VERY_LOW = "Very Low"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    VERY_HIGH = "Very High"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    CHOPPY = "choppy"
    BREAKOUT = "breakout"


class SetupStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    WAITING_CONFIRMATION = "waiting_confirmation"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class SetupGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D = "D"
    F = "F"


# ─── Scoring Weights ────────────────────────────────────────

DEFAULT_SCORING_WEIGHTS = {
    "market_structure": 25,
    "fvg_alignment": 20,
    "order_block_presence": 20,
    "smt_confirmation": 20,
    "liquidity_sweep": 10,
    "session_alignment": 5,
}  # Total: 100


def score_to_grade(score: float) -> str:
    """Convert numeric score (0-100) to letter grade."""
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 85:
        return "A-"
    elif score >= 80:
        return "B+"
    elif score >= 75:
        return "B"
    elif score >= 70:
        return "B-"
    elif score >= 65:
        return "C+"
    elif score >= 60:
        return "C"
    elif score >= 55:
        return "C-"
    elif score >= 50:
        return "D"
    else:
        return "F"


def score_to_confidence(score: float) -> str:
    """Convert numeric score to confidence label."""
    if score >= 85:
        return "Very High"
    elif score >= 70:
        return "High"
    elif score >= 55:
        return "Medium"
    elif score >= 40:
        return "Low"
    else:
        return "Very Low"


def grade_to_min_score(grade: str) -> float:
    """Convert letter grade back to minimum score threshold."""
    thresholds = {
        "A+": 95, "A": 90, "A-": 85,
        "B+": 80, "B": 75, "B-": 70,
        "C+": 65, "C": 60, "C-": 55,
        "D": 50, "F": 0,
    }
    return thresholds.get(grade, 0)


# ─── Market Bias ────────────────────────────────────────────

@dataclass
class MarketBias:
    """Aggregated directional bias from all engine evidence.

    Combines confluence snapshot evidence into a structured
    directional bias with strength, confidence, and grade.
    """
    instrument: str
    timeframe: str
    timestamp: datetime
    direction: str = "neutral"
    strength_score: float = 0.0
    confidence: str = "Very Low"
    trend: str = "neutral"
    market_regime: str = "ranging"
    session: str = "unknown"
    bias_grade: str = "F"
    supporting_evidence: list[dict] = field(default_factory=list)
    contradicting_evidence: list[dict] = field(default_factory=list)
    snapshot_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "direction": self.direction,
            "strength_score": self.strength_score,
            "confidence": self.confidence,
            "trend": self.trend,
            "market_regime": self.market_regime,
            "session": self.session,
            "bias_grade": self.bias_grade,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "snapshot_id": self.snapshot_id,
        }


# ─── Trade Setup ─────────────────────────────────────────────

@dataclass
class TradeSetup:
    """A deterministic trade setup — advisory only.

    Generated from Market Bias + engine evidence. Contains entry zone,
    targets, stop reference — but does NOT execute orders.
    """
    instrument: str
    timeframe: str
    direction: str
    status: str = "pending"

    # Entry
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    preferred_entry: float | None = None

    # Risk reference (not position sizing)
    stop_reference: float | None = None

    # Targets
    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None

    # Confirmation
    required_confirmation: list[str] = field(default_factory=list)

    # Evidence
    market_bias: MarketBias | None = None
    supporting_evidence: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)

    # Scoring
    setup_score: float = 0.0
    setup_grade: str = "F"

    # Metadata
    setup_id: str = field(default_factory=lambda: str(uuid4()))
    strategy_version: str = "1.0.0"
    generated_timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "setup_id": self.setup_id,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "status": self.status,
            "entry_zone_low": self.entry_zone_low,
            "entry_zone_high": self.entry_zone_high,
            "preferred_entry": self.preferred_entry,
            "stop_reference": self.stop_reference,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "target_3": self.target_3,
            "required_confirmation": self.required_confirmation,
            "market_bias": self.market_bias.to_dict() if self.market_bias else None,
            "supporting_evidence": self.supporting_evidence,
            "contradictions": self.contradictions,
            "setup_score": self.setup_score,
            "setup_grade": self.setup_grade,
            "strategy_version": self.strategy_version,
            "generated_timestamp": self.generated_timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


# ─── Strategy Rule ──────────────────────────────────────────

@dataclass
class StrategyRule:
    """A configurable rule for evaluating trade setups.

    Rules have required and optional conditions, weights,
    and minimum score thresholds. No hard-coded values.
    """
    name: str
    description: str = ""
    direction: str = "neutral"  # bullish, bearish, neutral
    required_conditions: list[dict] = field(default_factory=list)
    optional_conditions: list[dict] = field(default_factory=list)
    min_score: float = 60.0
    group: str = "default"
    priority: int = 0
    weight: float = 1.0
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "direction": self.direction,
            "required_conditions": self.required_conditions,
            "optional_conditions": self.optional_conditions,
            "min_score": self.min_score,
            "group": self.group,
            "priority": self.priority,
            "weight": self.weight,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StrategyRule:
        return cls(**{k: v for k, v in d.items()
                     if k in cls.__dataclass_fields__})


# ─── Strategy Config ────────────────────────────────────────

@dataclass
class StrategyConfig:
    """Configuration for the Strategy Engine.

    All parameters are externalized — nothing hard-coded.
    """
    enabled: bool = True
    min_setup_score: float = 50.0
    require_all_required: bool = True
    min_optional_count: int = 2
    scoring_weights: dict = field(default_factory=lambda: dict(DEFAULT_SCORING_WEIGHTS))
    rules: list[StrategyRule] = field(default_factory=list)
    setup_expiry_minutes: int = 60
    max_targets: int = 3
    entry_zone_width_pct: float = 0.2  # % of price for entry zone width
    stop_buffer_pct: float = 0.1

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "min_setup_score": self.min_setup_score,
            "require_all_required": self.require_all_required,
            "min_optional_count": self.min_optional_count,
            "scoring_weights": self.scoring_weights,
            "rules": [r.to_dict() for r in self.rules],
            "setup_expiry_minutes": self.setup_expiry_minutes,
            "max_targets": self.max_targets,
            "entry_zone_width_pct": self.entry_zone_width_pct,
            "stop_buffer_pct": self.stop_buffer_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StrategyConfig:
        rules = [StrategyRule.from_dict(r) for r in d.get("rules", [])]
        return cls(**{k: v for k, v in d.items() if k != "rules"}, rules=rules)


# ─── Market Bias Engine ─────────────────────────────────────

def build_market_bias(
    instrument: str,
    timeframe: str,
    timestamp: datetime,
    confluence_data: dict,
    ms_events: list[dict] | None = None,
    fvgs: list[dict] | None = None,
    order_blocks: list[dict] | None = None,
    smt_events: list[dict] | None = None,
    liquidity_events: list[dict] | None = None,
    session: str = "unknown",
    config: StrategyConfig | None = None,
) -> MarketBias:
    """Build a MarketBias from confluence + raw engine data.

    Args:
        instrument, timeframe, timestamp: Identifiers.
        confluence_data: Dict with keys like 'trend', 'swing_direction',
            'bullish_signals', 'bearish_signals', 'agreement_ratio', 'snapshot_id'.
        ms_events, fvgs, order_blocks, smt_events, liquidity_events:
            Raw engine outputs for evidence extraction.
        session: Current session.
        config: Strategy configuration.

    Returns:
        A MarketBias with direction, strength, confidence, and evidence.
    """
    if config is None:
        config = StrategyConfig()

    if ms_events is None:
        ms_events = []
    if fvgs is None:
        fvgs = []
    if order_blocks is None:
        order_blocks = []
    if smt_events is None:
        smt_events = []
    if liquidity_events is None:
        liquidity_events = []

    weights = config.scoring_weights

    # Determine predominant direction from confluence
    bullish_signals = float(confluence_data.get("bullish_signals", 0))
    bearish_signals = float(confluence_data.get("bearish_signals", 0))
    agreement = float(confluence_data.get("agreement_ratio", 0))
    trend = str(confluence_data.get("trend", "neutral"))
    swing = str(confluence_data.get("swing_direction", "neutral"))

    _direction, _bullish_score, _bearish_score, supporting, contradicting = _score_evidence(
        ms_events=ms_events,
        fvgs=fvgs,
        order_blocks=order_blocks,
        smt_events=smt_events,
        liquidity_events=liquidity_events,
        session=session,
        weights=weights,
    )

    # Strength = max of directional scores
    if _direction == "bullish":
        strength = _bullish_score
    elif _direction == "bearish":
        strength = _bearish_score
    else:
        strength = max(_bullish_score, _bearish_score)

    # Confidence from score
    confidence = score_to_confidence(strength)

    # Regime from trend
    regime = _determine_regime(trend, agreement)

    # Grade
    grade = score_to_grade(strength)

    return MarketBias(
        instrument=instrument,
        timeframe=timeframe,
        timestamp=timestamp,
        direction=_direction,
        strength_score=round(strength, 1),
        confidence=confidence,
        trend=trend,
        market_regime=regime,
        session=session,
        bias_grade=grade,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        snapshot_id=confluence_data.get("snapshot_id"),
    )


def _score_evidence(
    ms_events: list[dict],
    fvgs: list[dict],
    order_blocks: list[dict],
    smt_events: list[dict],
    liquidity_events: list[dict],
    session: str,
    weights: dict,
) -> tuple[str, float, float, list[dict], list[dict]]:
    """Score directional evidence from all engines.

    Returns (direction, bullish_score, bearish_score, supporting, contradicting).
    """
    bullish = 0.0
    bearish = 0.0
    supporting: list[dict] = []
    contradicting: list[dict] = []

    # ── Market Structure ──
    ms_weight = weights.get("market_structure", 25)
    ms_bull = 0
    ms_bear = 0
    for e in ms_events:
        d = str(e.get("direction", "")).lower()
        evt_type = str(e.get("event_type", "")).upper()
        if d == "bullish":
            ms_bull += 1
            supporting.append({"engine": "market_structure", "event": evt_type,
                               "direction": "bullish", "source_id": e.get("id")})
        elif d == "bearish":
            ms_bear += 1
            contradicting.append({"engine": "market_structure", "event": evt_type,
                                  "direction": "bearish", "source_id": e.get("id")})

    if ms_bull > 0:
        bullish += ms_weight
    if ms_bear > 0:
        bearish += ms_weight

    # ── FVGs ──
    fvg_weight = weights.get("fvg_alignment", 20)
    fvg_bull = 0
    fvg_bear = 0
    for f in fvgs:
        d = str(f.get("direction", "")).lower()
        status = str(f.get("status", "")).lower()
        if status not in ("active", "partially_filled"):
            continue
        if d == "bullish":
            fvg_bull += 1
            supporting.append({"engine": "fvg", "direction": "bullish",
                               "status": status, "source_id": f.get("id")})
        elif d == "bearish":
            fvg_bear += 1

    if fvg_bull > 0:
        bullish += fvg_weight
    if fvg_bear > 0:
        bearish += fvg_weight

    # But if direction is opposite of MS, they go to contradictions
    if bullish > 0 and fvg_bear > 0:
        for f in fvgs:
            if str(f.get("direction", "")).lower() == "bearish":
                contradicting.append({"engine": "fvg", "direction": "bearish",
                                      "source_id": f.get("id")})
    if bearish > 0 and fvg_bull > 0:
        for f in fvgs:
            if str(f.get("direction", "")).lower() == "bullish":
                contradicting.append({"engine": "fvg", "direction": "bullish",
                                      "source_id": f.get("id")})

    # ── Order Blocks ──
    ob_weight = weights.get("order_block_presence", 20)
    ob_bull = 0
    ob_bear = 0
    for ob in order_blocks:
        d = str(ob.get("direction", "")).lower()
        status = str(ob.get("status", "")).lower()
        if status in ("mitigated",):
            continue
        if d == "bullish":
            ob_bull += 1
            supporting.append({"engine": "order_block", "direction": "bullish",
                               "status": status, "source_id": ob.get("id")})
        elif d == "bearish":
            ob_bear += 1
            contradicting.append({"engine": "order_block", "direction": "bearish",
                                  "status": status, "source_id": ob.get("id")})

    if ob_bull > 0:
        bullish += ob_weight
    if ob_bear > 0:
        bearish += ob_weight

    # ── SMT ──
    smt_weight = weights.get("smt_confirmation", 20)
    smt_bull = 0
    smt_bear = 0
    for s in smt_events:
        d = str(s.get("direction", "")).lower()
        if d == "bullish":
            smt_bull += 1
            supporting.append({"engine": "smt", "direction": "bullish",
                               "source_id": s.get("id")})
        elif d == "bearish":
            smt_bear += 1
            contradicting.append({"engine": "smt", "direction": "bearish",
                                  "source_id": s.get("id")})

    if smt_bull > 0:
        bullish += smt_weight
    if smt_bear > 0:
        bearish += smt_weight

    # ── Liquidity Sweeps ──
    liq_weight = weights.get("liquidity_sweep", 10)
    sweep_bull = 0
    sweep_bear = 0
    for le in liquidity_events:
        d = str(le.get("direction", "")).lower()
        evt = str(le.get("event_type", "")).lower()
        if evt != "swept":
            continue
        if d == "bullish":
            sweep_bull += 1
            supporting.append({"engine": "liquidity", "event": "sweep",
                               "direction": "bullish", "source_id": le.get("id")})
        elif d == "bearish":
            sweep_bear += 1

    if sweep_bull > 0:
        bullish += liq_weight
    if sweep_bear > 0:
        bearish += liq_weight

    # ── Session Alignment ──
    sess_weight = weights.get("session_alignment", 5)
    high_activity = {"london", "ny_am", "ny_pm"}
    if session.lower() in high_activity:
        bullish += sess_weight
        bearish += sess_weight
        supporting.append({"engine": "session", "event": "high_activity",
                           "session": session})

    # ── Determine direction ──
    if bullish > bearish:
        direction = "bullish"
    elif bearish > bullish:
        direction = "bearish"
    else:
        direction = "neutral"

    return direction, bullish, bearish, supporting, contradicting


def _determine_regime(trend: str, agreement: float) -> str:
    """Determine market regime from trend and agreement."""
    if trend == "bullish" or trend == "bearish":
        if agreement >= 0.7:
            return "trending"
        else:
            return "breakout"
    elif trend == "choppy":
        return "choppy"
    else:
        return "ranging"


# ─── Trade Setup Generator ──────────────────────────────────

def generate_trade_setup(
    bias: MarketBias,
    order_blocks: list[dict] | None = None,
    fvgs: list[dict] | None = None,
    liquidity_levels: list[dict] | None = None,
    swi_points: list[dict] | None = None,
    config: StrategyConfig | None = None,
) -> TradeSetup:
    """Generate an advisory trade setup from Market Bias.

    Uses active order blocks for entry zone, FVGs for targets,
    liquidity levels for additional targets, and swing points
    for stop reference.

    This does NOT execute orders — advisory only.
    """
    if config is None:
        config = StrategyConfig()

    setup = TradeSetup(
        instrument=bias.instrument,
        timeframe=bias.timeframe,
        direction=bias.direction,
        market_bias=bias,
        setup_score=bias.strength_score,
        setup_grade=bias.bias_grade,
        expires_at=bias.timestamp + timedelta(minutes=config.setup_expiry_minutes),
        required_confirmation=[],
    )

    obs = order_blocks or []
    fvg_list = fvgs or []
    liq_levels = liquidity_levels or []
    swings = swi_points or []

    # ── Entry Zone from Order Blocks ──
    matching_obs = [ob for ob in obs
                    if str(ob.get("direction", "")).lower() == bias.direction
                    and str(ob.get("status", "")).lower() in ("active", "touched", "partially_mitigated")]

    if matching_obs:
        best_ob = matching_obs[0]  # First active OB
        ob_high = float(best_ob.get("price_high", 0) or best_ob.get("price_level", 0))
        ob_low = float(best_ob.get("price_low", 0) or best_ob.get("price_level", 0))
        ob_price = float(best_ob.get("price_level", max(ob_high, ob_low)))

        # Entry zone around the OB
        if bias.direction == "bullish":
            setup.entry_zone_low = round(ob_low, 2)
            setup.entry_zone_high = round(ob_high, 2)
            setup.preferred_entry = round((ob_high + ob_low) / 2, 2)
        else:
            setup.entry_zone_low = round(ob_low, 2)
            setup.entry_zone_high = round(ob_high, 2)
            setup.preferred_entry = round((ob_high + ob_low) / 2, 2)

        setup.supporting_evidence.append({
            "type": "order_block_entry",
            "source_id": best_ob.get("id"),
            "direction": bias.direction,
            "zone": [setup.entry_zone_low, setup.entry_zone_high],
        })

    # ── Stop Reference from Swing Points ──
    if swings:
        if bias.direction == "bullish":
            swing_lows = [s for s in swings
                          if str(s.get("swing_type", "")).lower() in ("low", "ll", "hl")]
            if swing_lows:
                lowest = min(swing_lows, key=lambda s: float(s.get("price", 0)))
                setup.stop_reference = round(float(lowest.get("price", 0)) * (1 - config.stop_buffer_pct), 2)
        else:
            swing_highs = [s for s in swings
                           if str(s.get("swing_type", "")).lower() in ("high", "hh", "lh")]
            if swing_highs:
                highest = max(swing_highs, key=lambda s: float(s.get("price", 0)))
                setup.stop_reference = round(float(highest.get("price", 0)) * (1 + config.stop_buffer_pct), 2)

    # ── Targets from FVGs + Liquidity ──
    targets: list[float] = []

    # FVG targets: far side of FVG
    for f in fvg_list:
        d = str(f.get("direction", "")).lower()
        status = str(f.get("status", "")).lower()
        if status not in ("active", "partially_filled"):
            continue
        if bias.direction == "bullish" and d == "bullish":
            # Target: high of the FVG
            tgt = float(f.get("gap_high", 0))
            if tgt > 0 and setup.preferred_entry and tgt > setup.preferred_entry:
                targets.append(tgt)
        elif bias.direction == "bearish" and d == "bearish":
            tgt = float(f.get("gap_low", 0))
            if tgt > 0 and setup.preferred_entry and tgt < setup.preferred_entry:
                targets.append(tgt)

    # Liquidity targets
    for ll in liq_levels:
        lvl = float(ll.get("price_level", 0))
        if lvl <= 0:
            continue
        if bias.direction == "bullish" and setup.preferred_entry and lvl > setup.preferred_entry:
            targets.append(lvl)
        elif bias.direction == "bearish" and setup.preferred_entry and lvl < setup.preferred_entry:
            targets.append(lvl)

    # Sort, deduplicate, pick top N
    if bias.direction == "bullish":
        targets = sorted(set(round(t, 2) for t in targets))
    else:
        targets = sorted(set(round(t, 2) for t in targets), reverse=True)

    n_targets = min(config.max_targets, len(targets))
    if n_targets >= 1:
        setup.target_1 = targets[0]
    if n_targets >= 2:
        setup.target_2 = targets[1]
    if n_targets >= 3:
        setup.target_3 = targets[2]

    # ── Required Confirmations ──
    if not matching_obs:
        setup.required_confirmation.append("wait_for_order_block")
    if setup.stop_reference is None:
        setup.required_confirmation.append("wait_for_stop_reference")

    # ── Status ──
    if not matching_obs or setup.stop_reference is None:
        setup.status = "waiting_confirmation"
    elif setup.setup_score >= config.min_setup_score:
        setup.status = "ready"
    else:
        setup.status = "pending"

    # ── Contradictions ──
    if bias.contradicting_evidence:
        setup.contradictions = list(bias.contradicting_evidence)

    return setup


# ─── Rule Engine ────────────────────────────────────────────

def evaluate_strategy_rules(
    setup: TradeSetup,
    rules: list[StrategyRule] | None = None,
    config: StrategyConfig | None = None,
) -> list[dict]:
    """Evaluate strategy rules against a Trade Setup.

    Returns list of rule evaluation results with matched/failed status.
    """
    if config is None:
        config = StrategyConfig()
    if rules is None:
        rules = config.rules

    results = []
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.direction != "neutral" and rule.direction != setup.direction:
            continue

        required_met = 0
        required_total = len(rule.required_conditions)
        for cond in rule.required_conditions:
            if _check_condition(setup, cond):
                required_met += 1

        optional_met = 0
        optional_total = len(rule.optional_conditions)
        for cond in rule.optional_conditions:
            if _check_condition(setup, cond):
                optional_met += 1

        # Evaluation
        passed = True
        if config.require_all_required and required_met < required_total:
            passed = False
        if optional_met < config.min_optional_count:
            passed = False
        if setup.setup_score < rule.min_score:
            passed = False

        results.append({
            "rule_name": rule.name,
            "direction": rule.direction,
            "passed": passed,
            "required_met": required_met,
            "required_total": required_total,
            "optional_met": optional_met,
            "optional_total": optional_total,
            "min_score": rule.min_score,
            "setup_score": setup.setup_score,
            "priority": rule.priority,
            "group": rule.group,
        })

    results.sort(key=lambda r: (-r["priority"], -r["setup_score"]))
    return results


def _check_condition(setup: TradeSetup, cond: dict) -> bool:
    """Check a single condition against a setup.

    condition format: {"field": "direction", "op": "eq", "value": "bullish"}
    Supported fields: direction, bias_direction, status, setup_grade,
                      has_entry_zone, has_stop, has_targets
    """
    field = cond.get("field", "")
    op = cond.get("op", "eq")
    value = cond.get("value")

    # Resolve field
    if field == "direction":
        actual = setup.direction
    elif field == "bias_direction":
        actual = setup.market_bias.direction if setup.market_bias else "neutral"
    elif field == "status":
        actual = setup.status
    elif field == "setup_grade":
        actual = setup.setup_grade
    elif field == "has_entry_zone":
        actual = setup.entry_zone_low is not None and setup.entry_zone_high is not None
    elif field == "has_stop":
        actual = setup.stop_reference is not None
    elif field == "has_targets":
        actual = setup.target_1 is not None
    elif field == "setup_score":
        actual = setup.setup_score
    else:
        return False

    # Evaluate
    if op == "eq":
        return str(actual).lower() == str(value).lower()
    elif op == "neq":
        return str(actual).lower() != str(value).lower()
    elif op == "gt":
        return float(actual) > float(value)
    elif op == "gte":
        return float(actual) >= float(value)
    elif op == "lt":
        return float(actual) < float(value)
    elif op == "lte":
        return float(actual) <= float(value)
    elif op == "in":
        return str(actual).lower() in [v.strip().lower() for v in str(value).split(",")]

    return False


# ─── Default Rules ──────────────────────────────────────────

def _default_strategy_rules() -> list[StrategyRule]:
    """Default strategy rules for bullish/bearish setups."""
    return [
        StrategyRule(
            name="bullish_high_confidence",
            description="Bullish setup with strong confluence and confirmation",
            direction="bullish",
            required_conditions=[
                {"field": "direction", "op": "eq", "value": "bullish"},
                {"field": "has_entry_zone", "op": "eq", "value": True},
                {"field": "has_stop", "op": "eq", "value": True},
            ],
            optional_conditions=[
                {"field": "has_targets", "op": "eq", "value": True},
                {"field": "status", "op": "eq", "value": "ready"},
            ],
            min_score=70, group="high_confidence", priority=10,
        ),
        StrategyRule(
            name="bearish_high_confidence",
            description="Bearish setup with strong confluence and confirmation",
            direction="bearish",
            required_conditions=[
                {"field": "direction", "op": "eq", "value": "bearish"},
                {"field": "has_entry_zone", "op": "eq", "value": True},
                {"field": "has_stop", "op": "eq", "value": True},
            ],
            optional_conditions=[
                {"field": "has_targets", "op": "eq", "value": True},
                {"field": "status", "op": "eq", "value": "ready"},
            ],
            min_score=70, group="high_confidence", priority=10,
        ),
        StrategyRule(
            name="pending_setup",
            description="Setup waiting for more evidence",
            direction="neutral",
            required_conditions=[
                {"field": "status", "op": "in", "value": "pending,waiting_confirmation"},
            ],
            optional_conditions=[],
            min_score=0, group="monitoring", priority=5, weight=0.5,
        ),
    ]
