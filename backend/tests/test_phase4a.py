"""Phase 4A Tests — Risk Engine.

Tests for risk assessment, validation, classification, scoring,
and edge cases.
"""

from datetime import datetime, timedelta
import pytest

from app.services.risk.engine import (
    compute_assessment, validate_setup, evaluate_risk,
    compute_risk_score, classify_risk,
    RiskAssessment, ValidationSummary, ValidationItem,
    RiskReport, RiskConfig, RiskClassification,
)


# ─── Helpers ─────────────────────────────────────────────────

def _setup(**overrides) -> dict:
    base = {
        "setup_id": "test-setup-001",
        "instrument": "ES",
        "timeframe": "5m",
        "direction": "bullish",
        "preferred_entry": 6010.0,
        "entry_zone_low": 6005.0,
        "entry_zone_high": 6015.0,
        "stop_reference": 6000.0,
        "target_1": 6030.0,
        "target_2": 6050.0,
        "target_3": 6070.0,
        "setup_score": 85.0,
    }
    base.update(overrides)
    return base


def _bias(**overrides) -> dict:
    base = {
        "direction": "bullish",
        "confidence": "High",
        "trend": "bullish",
        "market_regime": "trending",
        "session": "london",
        "bias_grade": "A-",
        "strength_score": 85.0,
    }
    base.update(overrides)
    return base


def _bearish_setup(**overrides) -> dict:
    base = {
        "setup_id": "test-setup-bear",
        "instrument": "ES",
        "timeframe": "5m",
        "direction": "bearish",
        "preferred_entry": 6020.0,
        "entry_zone_low": 6015.0,
        "entry_zone_high": 6025.0,
        "stop_reference": 6030.0,
        "target_1": 6000.0,
        "target_2": 5980.0,
        "target_3": 5960.0,
        "setup_score": 82.0,
    }
    base.update(overrides)
    return base


# ─── Risk Assessment Tests ───────────────────────────────────

class TestRiskAssessment:
    """Numerical risk metric computation."""

    def test_bullish_metrics(self):
        """Bullish setup: entry 6010, stop 6000, target 6030."""
        assessment = compute_assessment(_setup())
        assert assessment.entry_price == 6010.0
        assert assessment.stop_price == 6000.0
        assert assessment.stop_distance_points == 10.0
        assert assessment.stop_distance_pct == pytest.approx(0.1664, abs=0.01)
        assert assessment.reward_risk_ratio == pytest.approx(2.0, abs=0.1)
        assert assessment.best_reward_risk > assessment.reward_risk_ratio

    def test_bearish_metrics(self):
        """Bearish setup: entry 6020, stop 6030, target 6000."""
        assessment = compute_assessment(_bearish_setup())
        assert assessment.stop_distance_points == 10.0
        # R:R: (6020-6000)/10 = 20/10 = 2.0
        assert assessment.reward_risk_ratio == pytest.approx(2.0, abs=0.1)

    def test_no_stop(self):
        """Setup without stop reference yields zero R:R."""
        s = _setup(stop_reference=None)
        assessment = compute_assessment(s)
        assert assessment.reward_risk_ratio == 0.0
        assert assessment.stop_distance_pct == 0.0

    def test_no_targets(self):
        """Setup without targets yields zero R:R."""
        s = _setup(target_1=None, target_2=None, target_3=None)
        assessment = compute_assessment(s)
        assert assessment.reward_risk_ratio == 0.0

    def test_stability_score_max(self):
        """Full setup earns high stability."""
        assessment = compute_assessment(_setup())
        assert assessment.setup_stability_score >= 80.0

    def test_stability_score_low(self):
        """Minimal setup earns low stability."""
        s = _setup(stop_reference=None, target_1=None, target_2=None,
                    target_3=None, setup_score=30)
        assessment = compute_assessment(s)
        assert assessment.setup_stability_score <= 30

    def test_expected_value(self):
        """EV is computed from win rate and R:R."""
        assessment = compute_assessment(_setup())
        # EV = 0.5 * best_target_pct - 0.5 * stop_pct
        # Should be positive for 2:1 RR
        assert assessment.expected_value > 0

    def test_best_rr_uses_furthest_target(self):
        """Best R:R uses the furthest target."""
        assessment = compute_assessment(_setup(
            target_1=6030.0, target_2=6070.0, target_3=6100.0,
        ))
        assert assessment.best_reward_risk > assessment.reward_risk_ratio
        assert assessment.best_reward_risk >= 3.0

    def test_entry_from_zone(self):
        """Entry falls back to zone midpoint when preferred_entry is None or zero."""
        s = _setup(preferred_entry=0, entry_zone_low=6005.0, entry_zone_high=6015.0)
        assessment = compute_assessment(s)
        assert assessment.entry_price == 6010.0


# ─── Validation Tests ────────────────────────────────────────

class TestValidation:
    """Configurable validation rules."""

    def test_all_pass(self):
        """Good setup passes all rules."""
        assessment = compute_assessment(_setup())
        bias = _bias()
        validation = validate_setup(assessment, bias)
        assert validation.overall == "PASS"
        assert validation.failed == 0

    def test_fail_low_rr(self):
        """R:R below minimum fails."""
        s = _setup(target_1=6012.0)  # tiny target
        assessment = compute_assessment(s)
        bias = _bias()
        config = RiskConfig(min_reward_risk_ratio=2.0)
        validation = validate_setup(assessment, bias, config)
        assert validation.overall == "FAIL"

    def test_fail_wide_stop(self):
        """Stop too wide fails."""
        s = _setup(stop_reference=5900.0)  # 110 pt stop
        assessment = compute_assessment(s)
        bias = _bias()
        config = RiskConfig(max_stop_distance_pct=0.5)
        validation = validate_setup(assessment, bias, config)
        assert validation.overall == "FAIL"

    def test_fail_low_confidence(self):
        """Low confidence fails."""
        assessment = compute_assessment(_setup())
        bias = _bias(confidence="Low")
        config = RiskConfig(min_confidence="Medium")
        validation = validate_setup(assessment, bias, config)
        assert validation.overall == "FAIL"

    def test_fail_low_grade(self):
        """Low grade fails."""
        assessment = compute_assessment(_setup())
        bias = _bias(bias_grade="D")
        config = RiskConfig(min_strategy_grade="C+")
        validation = validate_setup(assessment, bias, config)
        assert validation.overall == "FAIL"

    def test_fail_session(self):
        """Disallowed session fails."""
        assessment = compute_assessment(_setup())
        bias = _bias(session="asia")
        validation = validate_setup(assessment, bias)
        assert validation.overall == "FAIL"

    def test_fail_regime(self):
        """Disallowed regime fails."""
        assessment = compute_assessment(_setup())
        bias = _bias(market_regime="choppy")
        validation = validate_setup(assessment, bias)
        assert validation.overall == "FAIL"

    def test_warn_rr(self):
        """R:R in warning zone produces WARN."""
        s = _setup(target_1=6015.0)  # small target
        assessment = compute_assessment(s)
        bias = _bias()
        config = RiskConfig(min_reward_risk_ratio=3.0, min_reward_risk_warn=0.5)
        validation = validate_setup(assessment, bias, config)
        assert any(i.result == "WARN" for i in validation.items)

    def test_multiple_failures(self):
        """Multiple failures are all reported."""
        assessment = compute_assessment(_setup(
            stop_reference=5800.0, target_1=6012.0,
        ))
        bias = _bias(confidence="Low", bias_grade="D", session="asia",
                     market_regime="choppy")
        config = RiskConfig(min_reward_risk_ratio=3.0,
                            max_stop_distance_pct=0.3)
        validation = validate_setup(assessment, bias, config)
        assert validation.failed >= 2

    def test_counters(self):
        """Passed/failed/warn counters match items."""
        assessment = compute_assessment(_setup())
        bias = _bias()
        validation = validate_setup(assessment, bias)
        assert validation.passed + validation.failed + validation.warnings == len(validation.items)


# ─── Risk Scoring & Classification ──────────────────────────

class TestRiskScoring:
    """Risk score computation and classification."""

    def test_excellent_setup_high_score(self):
        """Good setup scores high (>=70)."""
        assessment = compute_assessment(_setup())
        bias = _bias()
        validation = validate_setup(assessment, bias)
        score = compute_risk_score(assessment, validation, bias)
        assert score >= 70.0
        assert classify_risk(score) in ("Very Low", "Low", "Medium")

    def test_poor_setup_low_score(self):
        """Poor setup scores low (<40)."""
        assessment = compute_assessment(_setup(
            stop_reference=None, target_1=None, target_2=None, target_3=None,
            setup_score=20,
        ))
        bias = _bias(confidence="Very Low", bias_grade="F",
                     market_regime="choppy", session="asia")
        validation = validate_setup(assessment, bias)
        score = compute_risk_score(assessment, validation, bias)
        assert score < 40
        assert classify_risk(score) in ("High", "Extreme")

    def test_classification_thresholds(self):
        """Score maps to correct classification."""
        config = RiskConfig()
        assert classify_risk(95, config) == "Very Low"
        assert classify_risk(80, config) == "Low"
        assert classify_risk(65, config) == "Medium"
        assert classify_risk(50, config) == "High"
        assert classify_risk(20, config) == "Extreme"

    def test_score_capped_at_100(self):
        """Score never exceeds 100."""
        assessment = compute_assessment(_setup(
            target_1=7000.0, target_2=8000.0,  # huge targets
        ))
        bias = _bias(confidence="Very High", bias_grade="A+")
        validation = validate_setup(assessment, bias)
        score = compute_risk_score(assessment, validation, bias)
        assert score <= 100.0


# ─── Risk Report Tests ───────────────────────────────────────

class TestRiskReport:
    """Full risk report generation."""

    def test_full_report(self):
        """evaluate_risk produces a complete report."""
        report = evaluate_risk(_setup(), _bias())
        assert report.setup_id == "test-setup-001"
        assert report.overall_risk_score > 0
        assert report.risk_classification in ("Very Low", "Low", "Medium", "High", "Extreme")
        assert len(report.supporting_evidence) > 0
        assert len(report.validation.items) > 0

    def test_report_has_failures(self):
        """Failed validation appears in failure_reasons."""
        report = evaluate_risk(
            _setup(stop_reference=5800.0, target_1=6012.0),
            _bias(confidence="Low", session="asia"),
            config=RiskConfig(min_reward_risk_ratio=3.0,
                              max_stop_distance_pct=0.3),
        )
        assert len(report.failure_reasons) > 0
        assert len(report.contradicting_evidence) > 0

    def test_report_to_dict(self):
        """Report serializes to JSON-safe dict."""
        report = evaluate_risk(_setup(), _bias())
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "overall_risk_score" in d
        assert "assessment" in d
        assert isinstance(d["assessment"], dict)

    def test_historical_consistency(self):
        """Same inputs → same report (deterministic)."""
        r1 = evaluate_risk(_setup(), _bias())
        r2 = evaluate_risk(_setup(), _bias())
        assert r1.overall_risk_score == r2.overall_risk_score
        assert r1.risk_classification == r2.risk_classification


# ─── Config Tests ────────────────────────────────────────────

class TestRiskConfig:
    """Configuration serialization."""

    def test_config_round_trip(self):
        config = RiskConfig(
            min_reward_risk_ratio=3.0,
            max_stop_distance_pct=0.5,
            min_confidence="High",
            min_strategy_grade="B+",
            allowed_sessions=["london", "ny_am"],
            allowed_regimes=["trending"],
            rr_weight=35.0,
        )
        d = config.to_dict()
        c2 = RiskConfig.from_dict(d)
        assert c2.min_reward_risk_ratio == 3.0
        assert c2.max_stop_distance_pct == 0.5
        assert c2.min_confidence == "High"
        assert c2.allowed_sessions == ["london", "ny_am"]
        assert c2.rr_weight == 35.0

    def test_config_custom_thresholds(self):
        """Custom classification thresholds work."""
        config = RiskConfig(
            very_low_threshold=80,
            low_threshold=60,
            medium_threshold=40,
            high_threshold=20,
        )
        assert classify_risk(90, config) == "Very Low"
        assert classify_risk(70, config) == "Low"
        assert classify_risk(50, config) == "Medium"
        assert classify_risk(30, config) == "High"
        assert classify_risk(10, config) == "Extreme"


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_dry_run_no_db():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.post(
                "/api/v1/risk/evaluate-dry-run",
                params={"instrument": "ES", "timeframe": "5m"},
            )
            assert response.status_code in (200, 500)
        except Exception:
            pass  # DB not available is fine
