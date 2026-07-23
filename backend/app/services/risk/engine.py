"""Risk Engine — evaluates Trade Setups against configurable risk criteria.

Consumes Trade Setup + Market Bias to produce Risk Reports with
validation, classification, and detailed scoring.

Advisory only — does NOT execute, size positions, or manage trades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import sqrt


# ─── Enums ───────────────────────────────────────────────────

class RiskClassification(str, Enum):
    VERY_LOW = "Very Low"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    EXTREME = "Extreme"


class ValidationResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


# ─── Risk Config ─────────────────────────────────────────────

@dataclass
class RiskConfig:
    """Fully configurable risk parameters — no hard-coded values."""

    # R:R thresholds
    min_reward_risk_ratio: float = 2.0
    min_reward_risk_warn: float = 1.5  # warn below this

    # Stop distance limits (as % of price)
    max_stop_distance_pct: float = 1.0       # 1% of entry
    max_stop_distance_warn_pct: float = 0.5  # warn above this

    # Confidence & grade thresholds
    min_confidence: str = "Medium"  # High, Medium, Low
    min_strategy_grade: str = "C+"  # A+, A, A-, B+, ...

    # Session rules (allowed sessions)
    allowed_sessions: list[str] = field(default_factory=lambda: [
        "london", "ny_am", "ny_pm",
    ])

    # Time restrictions (UTC hour range, None = no restriction)
    allowed_start_hour: int | None = None
    allowed_end_hour: int | None = None

    # Market regime restrictions
    allowed_regimes: list[str] = field(default_factory=lambda: [
        "trending", "breakout",
    ])

    # Volatility limits (ATR-based, as % of price)
    max_volatility_pct: float = 3.0
    volatility_warn_pct: float = 1.5

    # Risk classification score thresholds
    very_low_threshold: float = 90.0
    low_threshold: float = 75.0
    medium_threshold: float = 60.0
    high_threshold: float = 40.0
    # below high_threshold = EXTREME

    # Scoring weights for overall risk score
    rr_weight: float = 30.0
    stop_weight: float = 20.0
    confidence_weight: float = 15.0
    grade_weight: float = 10.0
    volatility_weight: float = 10.0
    regime_weight: float = 10.0
    session_weight: float = 5.0

    def to_dict(self) -> dict:
        return {
            "min_reward_risk_ratio": self.min_reward_risk_ratio,
            "min_reward_risk_warn": self.min_reward_risk_warn,
            "max_stop_distance_pct": self.max_stop_distance_pct,
            "max_stop_distance_warn_pct": self.max_stop_distance_warn_pct,
            "min_confidence": self.min_confidence,
            "min_strategy_grade": self.min_strategy_grade,
            "allowed_sessions": self.allowed_sessions,
            "allowed_start_hour": self.allowed_start_hour,
            "allowed_end_hour": self.allowed_end_hour,
            "allowed_regimes": self.allowed_regimes,
            "max_volatility_pct": self.max_volatility_pct,
            "volatility_warn_pct": self.volatility_warn_pct,
            "very_low_threshold": self.very_low_threshold,
            "low_threshold": self.low_threshold,
            "medium_threshold": self.medium_threshold,
            "high_threshold": self.high_threshold,
            "rr_weight": self.rr_weight,
            "stop_weight": self.stop_weight,
            "confidence_weight": self.confidence_weight,
            "grade_weight": self.grade_weight,
            "volatility_weight": self.volatility_weight,
            "regime_weight": self.regime_weight,
            "session_weight": self.session_weight,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RiskConfig:
        valid_keys = {k for k in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid_keys})


# ─── Confidence Numeric Map ─────────────────────────────────

_CONFIDENCE_ORDER = {
    "Very Low": 1, "Low": 2, "Medium": 3, "High": 4, "Very High": 5,
}

_GRADE_ORDER = {
    "F": 0, "D": 1, "C-": 2, "C": 3, "C+": 4,
    "B-": 5, "B": 6, "B+": 7, "A-": 8, "A": 9, "A+": 10,
}


def _confidence_numeric(label: str) -> int:
    return _CONFIDENCE_ORDER.get(label, 1)


def _grade_numeric(grade: str) -> int:
    return _GRADE_ORDER.get(grade, 0)


# ─── Risk Assessment ────────────────────────────────────────

@dataclass
class RiskAssessment:
    """Numerical risk metrics derived from a Trade Setup."""

    setup_id: str = ""
    entry_price: float = 0.0
    stop_price: float = 0.0
    stop_distance_points: float = 0.0
    stop_distance_pct: float = 0.0

    # Targets
    target_1_distance_pct: float = 0.0
    target_2_distance_pct: float | None = None
    target_3_distance_pct: float | None = None

    # R:R
    reward_risk_ratio: float = 0.0
    best_reward_risk: float = 0.0  # using furthest target

    # Estimates
    mfe_estimate: float = 0.0  # Maximum Favorable Excursion
    mae_estimate: float = 0.0  # Maximum Adverse Excursion
    expected_value: float = 0.0
    volatility_pct: float = 0.0  # ATR as % of price

    # Stability
    setup_stability_score: float = 0.0  # 0-100

    def to_dict(self) -> dict:
        return {
            "setup_id": self.setup_id,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "stop_distance_points": round(self.stop_distance_points, 2),
            "stop_distance_pct": round(self.stop_distance_pct, 4),
            "target_1_distance_pct": round(self.target_1_distance_pct, 4),
            "target_2_distance_pct": round(self.target_2_distance_pct, 4) if self.target_2_distance_pct else None,
            "target_3_distance_pct": round(self.target_3_distance_pct, 4) if self.target_3_distance_pct else None,
            "reward_risk_ratio": round(self.reward_risk_ratio, 2),
            "best_reward_risk": round(self.best_reward_risk, 2),
            "mfe_estimate": round(self.mfe_estimate, 2),
            "mae_estimate": round(self.mae_estimate, 2),
            "expected_value": round(self.expected_value, 4),
            "volatility_pct": round(self.volatility_pct, 4),
            "setup_stability_score": round(self.setup_stability_score, 1),
        }


def compute_assessment(
    setup: dict,
    volatility_pct: float = 0.0,
) -> RiskAssessment:
    """Compute risk metrics from a Trade Setup dict.

    Args:
        setup: Trade setup dict with entry_zone_low, entry_zone_high,
               preferred_entry, stop_reference, target_1/2/3,
               setup_score.
        volatility_pct: ATR as % of price (0 if unknown).

    Returns:
        RiskAssessment with all computed metrics.
    """
    entry = float(setup.get("preferred_entry", 0)
                  if setup.get("preferred_entry") not in (None, 0) else 0)
    if entry <= 0:
        entry_low = float(setup.get("entry_zone_low", 0) or 0)
        entry_high = float(setup.get("entry_zone_high", 0) or 0)
        entry = (entry_low + entry_high) / 2 if (entry_low + entry_high) > 0 else entry_low

    stop = float(setup.get("stop_reference", 0) or 0)
    direction = str(setup.get("direction", "bullish")).lower()

    # Stop distance
    if entry > 0 and stop > 0:
        if direction == "bullish":
            stop_dist_pts = entry - stop
        else:
            stop_dist_pts = stop - entry
        stop_dist_pct = (stop_dist_pts / entry) * 100 if entry > 0 else 0
    else:
        stop_dist_pts = 0.0
        stop_dist_pct = 0.0

    # Target distances
    t1 = float(setup.get("target_1", 0) or 0)
    t2 = float(setup.get("target_2", 0) or 0)
    t3 = float(setup.get("target_3", 0) or 0)

    def _target_pct(tgt: float) -> float:
        if tgt <= 0 or entry <= 0:
            return 0.0
        if direction == "bullish":
            return ((tgt - entry) / entry) * 100
        else:
            return ((entry - tgt) / entry) * 100

    t1_pct = _target_pct(t1)
    t2_pct = _target_pct(t2) if t2 > 0 else None
    t3_pct = _target_pct(t3) if t3 > 0 else None

    # R:R
    rr = (t1_pct / stop_dist_pct) if (stop_dist_pct > 0 and t1_pct > 0) else 0.0

    # Best R:R (furthest target)
    best_tgt_pct = max(filter(None, [t1_pct, t2_pct, t3_pct])) if any([t1_pct, t2_pct, t3_pct]) else 0.0
    best_rr = (best_tgt_pct / stop_dist_pct) if (stop_dist_pct > 0 and best_tgt_pct > 0) else 0.0

    # MFE/MAE estimates (simple: MFE = best target, MAE = stop distance)
    mfe = best_tgt_pct
    mae = stop_dist_pct

    # Expected value (simplified: assume 50% win rate for scoring)
    win_rate = 0.5
    avg_win = best_tgt_pct if best_tgt_pct > 0 else (t1_pct if t1_pct > 0 else 0)
    avg_loss = stop_dist_pct
    ev = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    # Stability score: how solid is the setup?
    # Factors: has entry, has stop, has targets, reasonable R:R, low volatility
    setup_score = float(setup.get("setup_score", 0))
    stability = 0.0
    if entry > 0:
        stability += 25
    if stop > 0:
        stability += 25
    if t1 > 0:
        stability += 20
    if rr >= 2.0:
        stability += 15
    if setup_score >= 70:
        stability += 15
    stability = min(stability, 100.0)

    return RiskAssessment(
        setup_id=str(setup.get("setup_id", "")),
        entry_price=entry,
        stop_price=stop,
        stop_distance_points=round(stop_dist_pts, 2),
        stop_distance_pct=stop_dist_pct,
        target_1_distance_pct=t1_pct,
        target_2_distance_pct=t2_pct,
        target_3_distance_pct=t3_pct,
        reward_risk_ratio=rr,
        best_reward_risk=best_rr,
        mfe_estimate=mfe,
        mae_estimate=mae,
        expected_value=ev,
        volatility_pct=volatility_pct,
        setup_stability_score=stability,
    )


# ─── Validation ─────────────────────────────────────────────

@dataclass
class ValidationItem:
    """Single validation check result."""
    rule: str
    result: str  # PASS, FAIL, WARN
    detail: str = ""
    expected: float | str | None = None
    actual: float | str | None = None


@dataclass
class ValidationSummary:
    """Aggregate validation results."""
    items: list[ValidationItem] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    overall: str = "PASS"

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "items": [
                {"rule": i.rule, "result": i.result, "detail": i.detail,
                 "expected": i.expected, "actual": i.actual}
                for i in self.items
            ],
        }


def validate_setup(
    assessment: RiskAssessment,
    bias: dict | None = None,
    config: RiskConfig | None = None,
) -> ValidationSummary:
    """Validate a setup against configurable risk rules.

    Args:
        assessment: Computed risk metrics.
        bias: Market bias dict (direction, confidence, grade, regime, session).
        config: Risk configuration.

    Returns:
        ValidationSummary with all checks.
    """
    if config is None:
        config = RiskConfig()

    checks: list[ValidationItem] = []

    # ── Reward/Risk ──
    if assessment.reward_risk_ratio >= config.min_reward_risk_ratio:
        checks.append(ValidationItem("min_reward_risk", "PASS",
            f"R:R {assessment.reward_risk_ratio:.2f} ≥ {config.min_reward_risk_ratio}",
            config.min_reward_risk_ratio, round(assessment.reward_risk_ratio, 2)))
    elif assessment.reward_risk_ratio >= config.min_reward_risk_warn:
        checks.append(ValidationItem("min_reward_risk", "WARN",
            f"R:R {assessment.reward_risk_ratio:.2f} between {config.min_reward_risk_warn}–{config.min_reward_risk_ratio}",
            config.min_reward_risk_ratio, round(assessment.reward_risk_ratio, 2)))
    elif assessment.reward_risk_ratio > 0:
        checks.append(ValidationItem("min_reward_risk", "FAIL",
            f"R:R {assessment.reward_risk_ratio:.2f} < {config.min_reward_risk_ratio}",
            config.min_reward_risk_ratio, round(assessment.reward_risk_ratio, 2)))
    else:
        checks.append(ValidationItem("min_reward_risk", "FAIL",
            "No valid R:R (missing entry/stop/target)",
            config.min_reward_risk_ratio, None))

    # ── Stop Distance ──
    if assessment.stop_distance_pct <= config.max_stop_distance_pct:
        checks.append(ValidationItem("max_stop_distance", "PASS",
            f"Stop {assessment.stop_distance_pct:.2f}% ≤ {config.max_stop_distance_pct}%",
            config.max_stop_distance_pct, round(assessment.stop_distance_pct, 4)))
    elif assessment.stop_distance_pct <= config.max_stop_distance_pct * 1.5:
        checks.append(ValidationItem("max_stop_distance", "WARN",
            f"Stop {assessment.stop_distance_pct:.2f}% > {config.max_stop_distance_pct}%",
            config.max_stop_distance_pct, round(assessment.stop_distance_pct, 4)))
    else:
        checks.append(ValidationItem("max_stop_distance", "FAIL",
            f"Stop {assessment.stop_distance_pct:.2f}% exceeds {config.max_stop_distance_pct}%",
            config.max_stop_distance_pct, round(assessment.stop_distance_pct, 4)))

    # ── Confidence ──
    if bias:
        conf = str(bias.get("confidence", "Very Low"))
        conf_val = _confidence_numeric(conf)
        min_conf_val = _confidence_numeric(config.min_confidence)
        if conf_val >= min_conf_val:
            checks.append(ValidationItem("min_confidence", "PASS",
                f"Confidence '{conf}' ≥ '{config.min_confidence}'",
                config.min_confidence, conf))
        else:
            checks.append(ValidationItem("min_confidence", "FAIL",
                f"Confidence '{conf}' < '{config.min_confidence}'",
                config.min_confidence, conf))

    # ── Strategy Grade ──
    if bias:
        grade = str(bias.get("bias_grade", "F"))
        grade_val = _grade_numeric(grade)
        min_grade_val = _grade_numeric(config.min_strategy_grade)
        if grade_val >= min_grade_val:
            checks.append(ValidationItem("min_strategy_grade", "PASS",
                f"Grade '{grade}' ≥ '{config.min_strategy_grade}'",
                config.min_strategy_grade, grade))
        else:
            checks.append(ValidationItem("min_strategy_grade", "FAIL",
                f"Grade '{grade}' < '{config.min_strategy_grade}'",
                config.min_strategy_grade, grade))

    # ── Session ──
    if bias:
        session = str(bias.get("session", "unknown")).lower()
        if session in [s.lower() for s in config.allowed_sessions]:
            checks.append(ValidationItem("session_allowed", "PASS",
                f"Session '{session}' is allowed",
                str(config.allowed_sessions), session))
        else:
            checks.append(ValidationItem("session_allowed", "FAIL",
                f"Session '{session}' not in allowed: {config.allowed_sessions}",
                str(config.allowed_sessions), session))

    # ── Market Regime ──
    if bias:
        regime = str(bias.get("market_regime", "ranging")).lower()
        if regime in [r.lower() for r in config.allowed_regimes]:
            checks.append(ValidationItem("regime_allowed", "PASS",
                f"Regime '{regime}' is allowed",
                str(config.allowed_regimes), regime))
        else:
            checks.append(ValidationItem("regime_allowed", "FAIL",
                f"Regime '{regime}' not in allowed: {config.allowed_regimes}",
                str(config.allowed_regimes), regime))

    # ── Volatility ──
    if assessment.volatility_pct > 0:
        if assessment.volatility_pct <= config.max_volatility_pct:
            checks.append(ValidationItem("volatility", "PASS",
                f"Volatility {assessment.volatility_pct:.2f}% ≤ {config.max_volatility_pct}%",
                config.max_volatility_pct, round(assessment.volatility_pct, 4)))
        elif assessment.volatility_pct <= config.max_volatility_pct * 1.5:
            checks.append(ValidationItem("volatility", "WARN",
                f"Volatility {assessment.volatility_pct:.2f}% elevated",
                config.max_volatility_pct, round(assessment.volatility_pct, 4)))
        else:
            checks.append(ValidationItem("volatility", "FAIL",
                f"Volatility {assessment.volatility_pct:.2f}% > {config.max_volatility_pct}%",
                config.max_volatility_pct, round(assessment.volatility_pct, 4)))

    # Aggregate
    passed = sum(1 for c in checks if c.result == "PASS")
    failed = sum(1 for c in checks if c.result == "FAIL")
    warnings = sum(1 for c in checks if c.result == "WARN")
    overall = "FAIL" if failed > 0 else ("WARN" if warnings > 0 else "PASS")

    return ValidationSummary(
        items=checks, passed=passed, failed=failed, warnings=warnings,
        overall=overall,
    )


# ─── Risk Scoring & Classification ──────────────────────────

def compute_risk_score(
    assessment: RiskAssessment,
    validation: ValidationSummary,
    bias: dict | None = None,
    config: RiskConfig | None = None,
) -> float:
    """Compute an overall risk score (0-100, higher = lower risk).

    Scoring is additive based on weighted components.
    """
    if config is None:
        config = RiskConfig()

    score = 0.0

    # ── R:R component (0–rr_weight) ──
    rr = assessment.reward_risk_ratio
    rr_score = min(rr / config.min_reward_risk_ratio, 2.0) * (config.rr_weight / 2)
    score += min(rr_score, config.rr_weight)

    # ── Stop distance component ──
    stop_pct = assessment.stop_distance_pct
    if stop_pct > 0:
        stop_ratio = config.max_stop_distance_pct / max(stop_pct, 0.01)
        stop_score = min(stop_ratio, 1.5) * (config.stop_weight / 1.5)
        score += min(stop_score, config.stop_weight)
    # else: 0

    # ── Confidence component ──
    if bias:
        conf = str(bias.get("confidence", "Very Low"))
        conf_val = _confidence_numeric(conf)
        score += (conf_val / 5) * config.confidence_weight

    # ── Grade component ──
    if bias:
        grade = str(bias.get("bias_grade", "F"))
        grade_val = _grade_numeric(grade)
        score += (grade_val / 10) * config.grade_weight

    # ── Volatility component ──
    if assessment.volatility_pct > 0:
        vol_ratio = config.max_volatility_pct / max(assessment.volatility_pct, 0.01)
        vol_score = min(vol_ratio, 1.5) * (config.volatility_weight / 1.5)
        score += min(vol_score, config.volatility_weight)

    # ── Regime component ──
    if bias:
        regime = str(bias.get("market_regime", "ranging")).lower()
        if regime in [r.lower() for r in config.allowed_regimes]:
            score += config.regime_weight

    # ── Session component ──
    if bias:
        session = str(bias.get("session", "unknown")).lower()
        if session in [s.lower() for s in config.allowed_sessions]:
            score += config.session_weight

    # Cap at 100
    return round(min(score, 100.0), 1)


def classify_risk(score: float, config: RiskConfig | None = None) -> str:
    """Classify a risk score into a category."""
    if config is None:
        config = RiskConfig()
    if score >= config.very_low_threshold:
        return "Very Low"
    elif score >= config.low_threshold:
        return "Low"
    elif score >= config.medium_threshold:
        return "Medium"
    elif score >= config.high_threshold:
        return "High"
    else:
        return "Extreme"


# ─── Risk Report ─────────────────────────────────────────────

@dataclass
class RiskReport:
    """Complete risk evaluation report."""

    setup_id: str = ""
    instrument: str = ""
    timeframe: str = ""
    direction: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Scores
    overall_risk_score: float = 0.0
    risk_classification: str = "Extreme"

    # Metrics
    assessment: RiskAssessment = field(default_factory=RiskAssessment)

    # Validation
    validation: ValidationSummary = field(default_factory=ValidationSummary)

    # Evidence
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)

    # Config snapshot
    config_snapshot: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "setup_id": self.setup_id,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "overall_risk_score": self.overall_risk_score,
            "risk_classification": self.risk_classification,
            "assessment": self.assessment.to_dict(),
            "validation": self.validation.to_dict(),
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "failure_reasons": self.failure_reasons,
        }


def evaluate_risk(
    setup: dict,
    bias: dict | None = None,
    volatility_pct: float = 0.0,
    config: RiskConfig | None = None,
) -> RiskReport:
    """Full risk evaluation pipeline.

    Args:
        setup: Trade setup dict from Strategy Engine.
        bias: Market bias dict.
        volatility_pct: ATR as % of entry price.
        config: Risk configuration.

    Returns:
        RiskReport with assessment, validation, classification.
    """
    if config is None:
        config = RiskConfig()

    # Compute metrics
    assessment = compute_assessment(setup, volatility_pct)

    # Validate
    validation = validate_setup(assessment, bias, config)

    # Score & classify
    score = compute_risk_score(assessment, validation, bias, config)
    classification = classify_risk(score, config)

    # Build evidence
    supporting: list[str] = []
    contradicting: list[str] = []
    failures: list[str] = []

    for item in validation.items:
        if item.result == "PASS":
            supporting.append(f"{item.rule}: {item.detail}")
        elif item.result == "FAIL":
            failures.append(f"{item.rule}: {item.detail}")
            contradicting.append(f"{item.rule}: {item.detail}")
        elif item.result == "WARN":
            supporting.append(f"[WARN] {item.rule}: {item.detail}")

    return RiskReport(
        setup_id=str(setup.get("setup_id", "")),
        instrument=str(setup.get("instrument", "")),
        timeframe=str(setup.get("timeframe", "")),
        direction=str(setup.get("direction", "")),
        timestamp=datetime.utcnow(),
        overall_risk_score=score,
        risk_classification=classification,
        assessment=assessment,
        validation=validation,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        failure_reasons=failures,
        config_snapshot=config.to_dict(),
    )
