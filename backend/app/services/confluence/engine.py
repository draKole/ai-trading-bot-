"""Confluence Engine — unified market state from all analysis engines.

Combines outputs from Market Structure, Liquidity, FVG, Order Block,
and SMT engines into a single ConfluenceSnapshot. A configurable
RuleEngine evaluates conditions without making trade decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TrendState(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    CHOPPY = "choppy"


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ─── Confluence Snapshot ─────────────────────────────────────

@dataclass
class ConfluenceSnapshot:
    """Unified market state at a point in time.

    Aggregates evidence from all Phase 1 & 2 engines into a single
    snapshot suitable for rule evaluation and historical replay.
    """

    instrument: str
    timeframe: str
    timestamp: datetime

    # Trend
    trend: str = "neutral"
    trend_confidence: float = 0.0  # 0-100

    # Market Structure
    ms_event_count: int = 0
    latest_bos: dict | None = None
    latest_choch: dict | None = None
    swing_direction: str = "neutral"
    ms_bullish_count: int = 0
    ms_bearish_count: int = 0

    # Liquidity
    liquidity_level_count: int = 0
    active_sweeps_count: int = 0
    active_sweeps_bullish: int = 0
    active_sweeps_bearish: int = 0
    nearest_liquidity_level: dict | None = None

    # FVGs
    fvg_active_count: int = 0
    fvg_bullish_count: int = 0
    fvg_bearish_count: int = 0
    fvg_mitigated_count: int = 0

    # Order Blocks
    ob_active_count: int = 0
    ob_bullish_count: int = 0
    ob_bearish_count: int = 0
    ob_mitigated_count: int = 0

    # SMT
    smt_active_count: int = 0
    smt_bullish_count: int = 0
    smt_bearish_count: int = 0

    # Session
    session: str = "unknown"
    session_aligned: bool = False

    # Aggregate signals
    bullish_signals: int = 0
    bearish_signals: int = 0
    neutral_signals: int = 0
    total_signals: int = 0
    agreement_ratio: float = 0.0  # max(bullish, bearish) / total

    # Metadata
    snapshot_period_start: datetime | None = None
    snapshot_period_end: datetime | None = None
    related_event_ids: list[int] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ─── Rule Definitions ────────────────────────────────────────

class ConditionOperator(str, Enum):
    ALL = "all"        # ALL conditions must match
    ANY = "any"        # ANY condition matches
    MAJORITY = "majority"  # >50% match
    MINIMUM = "minimum"    # At least N match


@dataclass
class RuleCondition:
    """A single condition evaluated against a snapshot.

    Attributes:
        field: Dot-notation path to snapshot field (e.g., "ms.bullish_count").
        operator: Comparison operator ("gt", "gte", "lt", "lte", "eq", "neq", "exists").
        value: Comparison value (or None for "exists" check).
        weight: Multiplier for this condition (default 1.0).
    """
    field: str
    operator: str  # gt, gte, lt, lte, eq, neq, exists
    value: float | str | bool | None = None
    weight: float = 1.0

    def to_dict(self) -> dict:
        return {"field": self.field, "operator": self.operator,
                "value": self.value, "weight": self.weight}

    @classmethod
    def from_dict(cls, d: dict) -> RuleCondition:
        return cls(**d)


@dataclass
class Rule:
    """A named rule evaluated against a confluence snapshot.

    A Rule is a collection of conditions with an evaluation operator.
    Rules describe market conditions — they don't make trade decisions.
    """
    name: str
    description: str = ""
    conditions: list[RuleCondition] = field(default_factory=list)
    operator: str = "all"  # all, any, majority, minimum
    min_matches: int = 1    # for "minimum" operator
    group: str = "default"
    weight: float = 1.0
    direction: str = "neutral"  # bullish, bearish, neutral
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "conditions": [c.to_dict() for c in self.conditions],
            "operator": self.operator,
            "min_matches": self.min_matches,
            "group": self.group,
            "weight": self.weight,
            "direction": self.direction,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Rule:
        conditions = [RuleCondition.from_dict(c) for c in d.get("conditions", [])]
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            conditions=conditions,
            operator=d.get("operator", "all"),
            min_matches=d.get("min_matches", 1),
            group=d.get("group", "default"),
            weight=d.get("weight", 1.0),
            direction=d.get("direction", "neutral"),
            enabled=d.get("enabled", True),
        )


@dataclass
class RuleResult:
    """Result of evaluating a single rule against a snapshot."""
    rule_name: str
    matched: bool
    direction: str
    matched_conditions: list[str]
    total_conditions: int
    match_count: int
    score: float = 0.0
    evidence: dict = field(default_factory=dict)


# ─── Confluence Config ───────────────────────────────────────

@dataclass
class ConfluenceConfig:
    """Configuration for the Confluence Engine.

    Attributes:
        time_window_seconds: How far back to look for active events.
        min_evidence_sources: Minimum number of engines that must contribute.
        session_alignment_required: Whether session matters for evaluation.
        trend_weight: Weight of market structure in agreement scoring.
        liquidity_weight: Weight of liquidity events.
        fvg_weight: Weight of FVGs.
        ob_weight: Weight of Order Blocks.
        smt_weight: Weight of SMT signals.
        enabled_timeframes: Timeframes to analyze.
        rules: List of Rule objects for evaluation.
    """
    time_window_seconds: float = 3600.0  # 1 hour default
    min_evidence_sources: int = 1
    session_alignment_required: bool = False
    trend_weight: float = 1.0
    liquidity_weight: float = 1.0
    fvg_weight: float = 0.8
    ob_weight: float = 1.2
    smt_weight: float = 1.5
    enabled_timeframes: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "time_window_seconds": self.time_window_seconds,
            "min_evidence_sources": self.min_evidence_sources,
            "session_alignment_required": self.session_alignment_required,
            "trend_weight": self.trend_weight,
            "liquidity_weight": self.liquidity_weight,
            "fvg_weight": self.fvg_weight,
            "ob_weight": self.ob_weight,
            "smt_weight": self.smt_weight,
            "enabled_timeframes": self.enabled_timeframes,
            "rules": [r.to_dict() for r in self.rules],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConfluenceConfig:
        rules = [Rule.from_dict(r) for r in d.get("rules", [])]
        return cls(**{k: v for k, v in d.items() if k != "rules"}, rules=rules)


# ─── Snapshot Builder ────────────────────────────────────────

def build_snapshot(
    instrument: str,
    timeframe: str,
    timestamp: datetime,
    ms_events: list[dict] | None = None,
    liquidity_events: list[dict] | None = None,
    fvgs: list[dict] | None = None,
    order_blocks: list[dict] | None = None,
    smt_events: list[dict] | None = None,
    session: str = "unknown",
    config: ConfluenceConfig | None = None,
) -> ConfluenceSnapshot:
    """Build a ConfluenceSnapshot from engine outputs.

    Args:
        instrument, timeframe, timestamp: Snapshot identifiers.
        ms_events: Market Structure events (BOS, CHoCH, swings).
        liquidity_events: Liquidity sweeps, breaks.
        fvgs: Active FVGs.
        order_blocks: Active Order Blocks.
        smt_events: Active SMT signals.
        session: Current session name.
        config: Confluence configuration.

    Returns:
        ConfluenceSnapshot with all aggregated evidence.
    """
    if config is None:
        config = ConfluenceConfig()

    snapshot = ConfluenceSnapshot(
        instrument=instrument,
        timeframe=timeframe,
        timestamp=timestamp,
        session=session,
        snapshot_period_start=datetime.fromtimestamp(
            timestamp.timestamp() - config.time_window_seconds
        ) if timestamp else None,
        snapshot_period_end=timestamp,
    )

    ms_events = ms_events or []
    liquidity_events = liquidity_events or []
    fvgs = fvgs or []
    order_blocks = order_blocks or []
    smt_events = smt_events or []

    # ── Market Structure ──
    snapshot.ms_event_count = len(ms_events)
    for e in ms_events:
        evt_type = str(e.get("event_type", "")).upper()
        direction = str(e.get("direction", "")).lower()
        if direction == "bullish":
            snapshot.ms_bullish_count += 1
        elif direction == "bearish":
            snapshot.ms_bearish_count += 1

        if evt_type == "BOS" and not snapshot.latest_bos:
            snapshot.latest_bos = dict(e)
        if evt_type in ("CHOCH", "CHoCH") and not snapshot.latest_choch:
            snapshot.latest_choch = dict(e)

    # Swing direction from aggregate
    if snapshot.ms_bullish_count > snapshot.ms_bearish_count:
        snapshot.swing_direction = "bullish"
    elif snapshot.ms_bearish_count > snapshot.ms_bullish_count:
        snapshot.swing_direction = "bearish"

    # Trend determination
    snapshot.trend = _determine_trend(snapshot)

    # ── Liquidity ──
    snapshot.liquidity_level_count = len(liquidity_events)
    for e in liquidity_events:
        evt_type = str(e.get("event_type", "")).lower()
        if evt_type == "swept":
            snapshot.active_sweeps_count += 1
            direction = str(e.get("direction", "")).lower()
            if direction == "bullish":
                snapshot.active_sweeps_bullish += 1
            elif direction == "bearish":
                snapshot.active_sweeps_bearish += 1

    # ── FVGs ──
    for f in fvgs:
        status = str(f.get("status", "")).lower()
        direction = str(f.get("direction", "")).lower()
        if status in ("active", "partially_filled"):
            snapshot.fvg_active_count += 1
            if direction == "bullish":
                snapshot.fvg_bullish_count += 1
            elif direction == "bearish":
                snapshot.fvg_bearish_count += 1
        elif status == "mitigated":
            snapshot.fvg_mitigated_count += 1

    # ── Order Blocks ──
    for ob in order_blocks:
        status = str(ob.get("status", "")).lower()
        direction = str(ob.get("direction", "")).lower()
        if status in ("active", "touched", "partially_mitigated"):
            snapshot.ob_active_count += 1
            if direction == "bullish":
                snapshot.ob_bullish_count += 1
            elif direction == "bearish":
                snapshot.ob_bearish_count += 1
        elif status == "mitigated":
            snapshot.ob_mitigated_count += 1

    # ── SMT ──
    for s in smt_events:
        direction = str(s.get("direction", "")).lower()
        snapshot.smt_active_count += 1
        if direction == "bullish":
            snapshot.smt_bullish_count += 1
        elif direction == "bearish":
            snapshot.smt_bearish_count += 1

    # ── Aggregate Signals ──
    snapshot.bullish_signals = (
        (1 if snapshot.swing_direction == "bullish" else 0) * config.trend_weight +
        (1 if snapshot.active_sweeps_bullish > 0 else 0) * config.liquidity_weight +
        (1 if snapshot.fvg_bullish_count > 0 else 0) * config.fvg_weight +
        (1 if snapshot.ob_bullish_count > 0 else 0) * config.ob_weight +
        (1 if snapshot.smt_bullish_count > 0 else 0) * config.smt_weight
    )

    snapshot.bearish_signals = (
        (1 if snapshot.swing_direction == "bearish" else 0) * config.trend_weight +
        (1 if snapshot.active_sweeps_bearish > 0 else 0) * config.liquidity_weight +
        (1 if snapshot.fvg_bearish_count > 0 else 0) * config.fvg_weight +
        (1 if snapshot.ob_bearish_count > 0 else 0) * config.ob_weight +
        (1 if snapshot.smt_bearish_count > 0 else 0) * config.smt_weight
    )

    snapshot.total_signals = snapshot.bullish_signals + snapshot.bearish_signals
    if snapshot.total_signals > 0:
        snapshot.agreement_ratio = max(snapshot.bullish_signals, snapshot.bearish_signals) / snapshot.total_signals

    # Session alignment
    snapshot.session_aligned = _is_session_aligned(session, snapshot)

    # Trend confidence
    snapshot.trend_confidence = snapshot.agreement_ratio * 100

    return snapshot


def _determine_trend(snapshot: ConfluenceSnapshot) -> str:
    """Determine trend from MS events."""
    if snapshot.ms_bullish_count > snapshot.ms_bearish_count * 1.5:
        return "bullish"
    elif snapshot.ms_bearish_count > snapshot.ms_bullish_count * 1.5:
        return "bearish"
    elif snapshot.ms_event_count == 0:
        return "neutral"
    else:
        return "choppy"


def _is_session_aligned(session: str, snapshot: ConfluenceSnapshot) -> bool:
    """Check if session is a high-activity session."""
    high_activity = {"london", "ny_am", "ny_pm"}
    return session.lower() in high_activity


# ─── Rule Engine ─────────────────────────────────────────────

def evaluate_rules(
    snapshot: ConfluenceSnapshot,
    rules: list[Rule] | None = None,
    config: ConfluenceConfig | None = None,
) -> list[RuleResult]:
    """Evaluate all rules against a confluence snapshot.

    Args:
        snapshot: The confluence snapshot to evaluate.
        rules: List of rules. If None, uses rules from config.
        config: Confluence config containing rules.

    Returns:
        List of RuleResult objects, one per rule.
    """
    if rules is None and config is not None:
        rules = config.rules
    if rules is None:
        rules = _default_rules()

    results = []
    for rule in rules:
        if not rule.enabled:
            continue

        match_count = 0
        matched_names = []
        evidence = {}

        for cond in rule.conditions:
            value = _extract_field(snapshot, cond.field)
            is_match = _evaluate_condition(value, cond.operator, cond.value)
            evidence[cond.field] = {"value": value, "expected": cond.value,
                                    "operator": cond.operator, "match": is_match}
            if is_match:
                match_count += 1
                matched_names.append(cond.field)

        total = len(rule.conditions)
        matched = False

        if rule.operator == "all":
            matched = match_count == total
        elif rule.operator == "any":
            matched = match_count > 0
        elif rule.operator == "majority":
            matched = match_count > total / 2
        elif rule.operator == "minimum":
            matched = match_count >= rule.min_matches

        score = (match_count / total * 100) if total > 0 else 0
        score *= rule.weight

        results.append(RuleResult(
            rule_name=rule.name,
            matched=matched,
            direction=rule.direction,
            matched_conditions=matched_names,
            total_conditions=total,
            match_count=match_count,
            score=score,
            evidence=evidence,
        ))

    return results


def _extract_field(snapshot: ConfluenceSnapshot, field_path: str):
    """Extract a field from a snapshot using dot notation.

    Supports short aliases:
        "ms.bullish_count" → snapshot.ms_bullish_count
        "liq.sweeps" → snapshot.active_sweeps_count
        "fvg.bullish" → snapshot.fvg_bullish_count
        "ob.active" → snapshot.ob_active_count
        "smt.bullish" → snapshot.smt_bullish_count
        "trend" → snapshot.trend
        "session_aligned" → snapshot.session_aligned
    """
    # Short aliases
    aliases = {
        "ms.bullish_count": "ms_bullish_count",
        "ms.bearish_count": "ms_bearish_count",
        "ms.event_count": "ms_event_count",
        "liq.sweeps": "active_sweeps_count",
        "liq.bullish_sweeps": "active_sweeps_bullish",
        "liq.bearish_sweeps": "active_sweeps_bearish",
        "fvg.active": "fvg_active_count",
        "fvg.bullish": "fvg_bullish_count",
        "fvg.bearish": "fvg_bearish_count",
        "ob.active": "ob_active_count",
        "ob.bullish": "ob_bullish_count",
        "ob.bearish": "ob_bearish_count",
        "smt.active": "smt_active_count",
        "smt.bullish": "smt_bullish_count",
        "smt.bearish": "smt_bearish_count",
        "swing_direction": "swing_direction",
        "trend": "trend",
        "session_aligned": "session_aligned",
    }

    resolved = aliases.get(field_path, field_path.replace(".", "_"))
    return getattr(snapshot, resolved, None)


def _evaluate_condition(value, operator: str, expected) -> bool:
    """Evaluate a single condition."""
    if operator == "exists":
        return value is not None and value != 0 and value != "" and value != "neutral"
    if value is None:
        return False

    try:
        if operator == "gt":
            return float(value) > float(expected)
        elif operator == "gte":
            return float(value) >= float(expected)
        elif operator == "lt":
            return float(value) < float(expected)
        elif operator == "lte":
            return float(value) <= float(expected)
        elif operator == "eq":
            if isinstance(expected, str):
                return str(value).lower() == expected.lower()
            return value == expected
        elif operator == "neq":
            if isinstance(expected, str):
                return str(value).lower() != expected.lower()
            return value != expected
    except (ValueError, TypeError):
        pass

    return False


def _default_rules() -> list[Rule]:
    """Default rules for bullish/bearish confluence."""
    return [
        Rule(
            name="bullish_bos_plus_fvg",
            description="Bullish BOS with bullish FVG",
            conditions=[
                RuleCondition("swing_direction", "eq", "bullish"),
                RuleCondition("fvg.bullish", "gt", 0),
            ],
            operator="all", direction="bullish", group="structure",
        ),
        Rule(
            name="bearish_bos_plus_fvg",
            description="Bearish BOS with bearish FVG",
            conditions=[
                RuleCondition("swing_direction", "eq", "bearish"),
                RuleCondition("fvg.bearish", "gt", 0),
            ],
            operator="all", direction="bearish", group="structure",
        ),
        Rule(
            name="liquidity_sweep_plus_ob",
            description="Liquidity sweep with active Order Block",
            conditions=[
                RuleCondition("liq.sweeps", "gt", 0),
                RuleCondition("ob.active", "gt", 0),
            ],
            operator="all", direction="neutral", group="liquidity",
        ),
        Rule(
            name="bullish_smt_present",
            description="Bullish SMT divergence active",
            conditions=[
                RuleCondition("smt.bullish", "gt", 0),
            ],
            operator="all", direction="bullish", group="smt",
        ),
        Rule(
            name="bearish_smt_present",
            description="Bearish SMT divergence active",
            conditions=[
                RuleCondition("smt.bearish", "gt", 0),
            ],
            operator="all", direction="bearish", group="smt",
        ),
        Rule(
            name="bullish_strong_confluence",
            description="Multiple bullish engines agree",
            conditions=[
                RuleCondition("swing_direction", "eq", "bullish"),
                RuleCondition("fvg.bullish", "gt", 0),
                RuleCondition("ob.bullish", "gt", 0),
                RuleCondition("smt.bullish", "gt", 0),
            ],
            operator="minimum", min_matches=2, direction="bullish", group="confluence",
        ),
        Rule(
            name="bearish_strong_confluence",
            description="Multiple bearish engines agree",
            conditions=[
                RuleCondition("swing_direction", "eq", "bearish"),
                RuleCondition("fvg.bearish", "gt", 0),
                RuleCondition("ob.bearish", "gt", 0),
                RuleCondition("smt.bearish", "gt", 0),
            ],
            operator="minimum", min_matches=2, direction="bearish", group="confluence",
        ),
    ]
