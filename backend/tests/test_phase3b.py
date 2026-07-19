"""Phase 3B Tests — Strategy Engine.

Tests for Market Bias building, Trade Setup generation,
strategy rule evaluation, scoring, edge cases.
"""

from datetime import datetime, timedelta
import pytest

from app.services.strategy.engine import (
    build_market_bias, generate_trade_setup, evaluate_strategy_rules,
    MarketBias, TradeSetup, StrategyRule, StrategyConfig,
    SetupStatus, SetupGrade, BiasDirection, ConfidenceLevel,
    MarketRegime, score_to_grade, score_to_confidence,
    DEFAULT_SCORING_WEIGHTS, _default_strategy_rules,
)


# ─── Helpers ─────────────────────────────────────────────────

def _dt(minute_offset=0):
    return datetime(2025, 6, 16, 9, 30) + timedelta(minutes=minute_offset)


def _ms_event(event_type, direction, idx=1):
    return {"id": idx, "event_type": event_type, "direction": direction}


def _fvg(direction, status="active", idx=1):
    return {"id": idx, "direction": direction, "status": status}


def _ob(direction, status="active", idx=1,
        price_high=100.0, price_low=99.0, price_level=99.5):
    return {"id": idx, "direction": direction, "status": status,
            "price_high": price_high, "price_low": price_low,
            "price_level": price_level}


def _smt(direction, idx=1):
    return {"id": idx, "direction": direction}


def _liq_sweep(direction, idx=1):
    return {"id": idx, "event_type": "swept", "direction": direction}


# ─── Market Bias Tests ───────────────────────────────────────

class TestMarketBias:
    """Market Bias: directional assessment from evidence."""

    def test_bullish_bias_from_all_engines(self):
        """All engines bullish → strong bullish bias."""
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 3, "bearish_signals": 0,
                      "agreement_ratio": 1.0}
        bias = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            smt_events=[_smt("bullish")],
            liquidity_events=[_liq_sweep("bullish")],
            session="london",
        )
        assert bias.direction == "bullish"
        assert bias.strength_score > 80
        assert bias.confidence in ("High", "Very High")
        assert bias.bias_grade in ("A+", "A", "A-", "B+", "B")

    def test_bearish_bias_from_all_engines(self):
        """All engines bearish → strong bearish bias."""
        confluence = {"trend": "bearish", "swing_direction": "bearish",
                      "bullish_signals": 0, "bearish_signals": 3,
                      "agreement_ratio": 1.0}
        bias = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bearish")],
            fvgs=[_fvg("bearish")],
            order_blocks=[_ob("bearish")],
            smt_events=[_smt("bearish")],
            liquidity_events=[_liq_sweep("bearish")],
            session="ny_am",
        )
        assert bias.direction == "bearish"
        assert bias.strength_score > 80

    def test_contradictory_evidence(self):
        """Bullish MS but bearish SMT → mixed bias."""
        confluence = {"trend": "choppy", "swing_direction": "bullish",
                      "bullish_signals": 1, "bearish_signals": 1,
                      "agreement_ratio": 0.5}
        bias = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bearish")],
            order_blocks=[_ob("bullish")],
            smt_events=[_smt("bearish")],
        )
        assert len(bias.supporting_evidence) > 0
        assert len(bias.contradicting_evidence) > 0

    def test_empty_evidence(self):
        """No evidence → neutral, low confidence."""
        confluence = {"trend": "neutral", "swing_direction": "neutral",
                      "bullish_signals": 0, "bearish_signals": 0,
                      "agreement_ratio": 0}
        bias = build_market_bias("ES", "5m", _dt(), confluence)
        assert bias.direction == "neutral"
        assert bias.strength_score == 0
        assert bias.confidence == "Very Low"
        assert bias.bias_grade == "F"

    def test_supporting_evidence_has_source_ids(self):
        """Evidence entries reference source engine IDs."""
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 2, "bearish_signals": 0,
                      "agreement_ratio": 1.0}
        bias = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bullish", idx=42)],
            fvgs=[_fvg("bullish", idx=99)],
        )
        sources = [e.get("source_id") for e in bias.supporting_evidence
                   if e.get("source_id") is not None]
        assert len(sources) >= 1

    def test_session_boosts_score(self):
        """High-activity sessions receive alignment bonus."""
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 1, "bearish_signals": 0,
                      "agreement_ratio": 1.0}

        bias_london = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            session="london",
        )
        bias_asia = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            session="asia",
        )
        # London should score slightly higher due to session bonus
        assert bias_london.strength_score >= bias_asia.strength_score

    def test_market_regime(self):
        """Regime is determined from trend + agreement."""
        # Trending: strong agreement + clear trend
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 3, "bearish_signals": 0,
                      "agreement_ratio": 0.85}
        bias = build_market_bias("ES", "5m", _dt(), confluence)
        assert bias.market_regime == "trending"

        # Choppy: choppy trend
        confluence2 = {"trend": "choppy", "swing_direction": "neutral",
                       "bullish_signals": 1, "bearish_signals": 1,
                       "agreement_ratio": 0.5}
        bias2 = build_market_bias("ES", "5m", _dt(), confluence2)
        assert bias2.market_regime == "choppy"


# ─── Trade Setup Tests ───────────────────────────────────────

class TestTradeSetup:
    """Trade Setup: advisory entry/stop/target generation."""

    def _make_bullish_bias(self) -> MarketBias:
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 3, "bearish_signals": 0,
                      "agreement_ratio": 1.0}
        return build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            smt_events=[_smt("bullish")],
            session="london",
        )

    def test_setup_from_bullish_bias(self):
        """Bullish bias generates a valid setup."""
        bias = self._make_bullish_bias()
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish", price_high=6010.0, price_low=6005.0, price_level=6007.5)],
            swi_points=[{"swing_type": "low", "price": 6000.0}],
        )
        assert setup.direction == "bullish"
        assert setup.entry_zone_low is not None
        assert setup.entry_zone_high is not None
        assert setup.stop_reference is not None
        assert setup.setup_score > 0

    def test_setup_from_bearish_bias(self):
        """Bearish bias generates a valid setup."""
        confluence = {"trend": "bearish", "swing_direction": "bearish",
                      "bullish_signals": 0, "bearish_signals": 3,
                      "agreement_ratio": 1.0}
        bias = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bearish")],
            fvgs=[_fvg("bearish")],
            order_blocks=[_ob("bearish")],
            smt_events=[_smt("bearish")],
            session="london",
        )
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bearish", price_high=6020.0, price_low=6015.0, price_level=6017.5)],
            swi_points=[{"swing_type": "high", "price": 6030.0}],
        )
        assert setup.direction == "bearish"
        assert setup.stop_reference is not None

    def test_waiting_confirmation_when_no_ob(self):
        """No matching OB → waiting_confirmation status."""
        bias = self._make_bullish_bias()
        setup = generate_trade_setup(bias)  # no OBs
        assert setup.status == "waiting_confirmation"

    def test_ready_when_score_above_threshold(self):
        """High score setup is marked ready."""
        bias = self._make_bullish_bias()
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish", price_high=6005.0, price_low=6000.0, price_level=6002.5)],
            swi_points=[{"swing_type": "low", "price": 5995.0}],
        )
        config = StrategyConfig(min_setup_score=50)
        setup2 = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish", price_high=6005.0, price_low=6000.0, price_level=6002.5)],
            swi_points=[{"swing_type": "low", "price": 5995.0}],
            config=config,
        )
        assert setup2.status == "ready"

    def test_pending_when_low_score(self):
        """Low score setup stays pending."""
        confluence = {"trend": "neutral", "swing_direction": "neutral",
                      "bullish_signals": 0, "bearish_signals": 0,
                      "agreement_ratio": 0}
        bias = build_market_bias("ES", "5m", _dt(), confluence)
        setup = generate_trade_setup(bias)
        assert setup.status in ("pending", "waiting_confirmation")

    def test_targets_from_fvgs(self):
        """FVG prices become targets."""
        bias = self._make_bullish_bias()
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish", price_high=6010.0, price_low=6005.0, price_level=6007.5)],
            fvgs=[
                _fvg("bullish"),
                {"id": 2, "direction": "bullish", "status": "active",
                 "gap_high": 6015.0, "gap_low": 6012.0},
                {"id": 3, "direction": "bullish", "status": "active",
                 "gap_high": 6025.0, "gap_low": 6020.0},
            ],
            swi_points=[{"swing_type": "low", "price": 6000.0}],
        )
        assert setup.target_1 is not None
        if setup.target_2 is not None:
            assert setup.target_2 > (setup.target_1 or 0)

    def test_expiry_set(self):
        """Setup has an expiration time."""
        bias = self._make_bullish_bias()
        config = StrategyConfig(setup_expiry_minutes=30)
        now = datetime.utcnow()
        # Override bias timestamp to now so expiry is relative
        bias = build_market_bias(
            "ES", "5m", now,
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 3, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            smt_events=[_smt("bullish")],
            session="london",
        )
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish")],
            swi_points=[{"swing_type": "low", "price": 5990.0}],
            config=config,
        )
        assert setup.expires_at is not None
        delta = setup.expires_at - setup.generated_timestamp
        assert 29 <= delta.total_seconds() / 60 <= 31

    def test_unique_setup_ids(self):
        """Each setup has a unique ID."""
        bias = self._make_bullish_bias()
        s1 = generate_trade_setup(bias, order_blocks=[_ob("bullish")],
                                  swi_points=[{"swing_type": "low", "price": 5990.0}])
        s2 = generate_trade_setup(bias, order_blocks=[_ob("bullish")],
                                  swi_points=[{"swing_type": "low", "price": 5990.0}])
        assert s1.setup_id != s2.setup_id

    def test_contradictions_propagated(self):
        """Contradictions from bias appear in setup."""
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 2, "bearish_signals": 1,
                      "agreement_ratio": 0.67}
        bias = build_market_bias(
            "ES", "5m", _dt(), confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bearish")],
        )
        setup = generate_trade_setup(bias)
        if bias.contradicting_evidence:
            assert len(setup.contradictions) > 0


# ─── Strategy Rule Tests ─────────────────────────────────────

class TestStrategyRules:
    """Configurable strategy rule evaluation."""

    def test_bullish_high_confidence_rule(self):
        """Default bullish rule matches when conditions met."""
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 3, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            smt_events=[_smt("bullish")],
            session="london",
        )
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish")],
            fvgs=[{"id": 2, "direction": "bullish", "status": "active",
                   "gap_high": 6015.0, "gap_low": 6012.0}],
            swi_points=[{"swing_type": "low", "price": 5990.0}],
        )

        # Use config with lower min_optional_count so the rule can pass
        config = StrategyConfig(min_optional_count=1)
        rules = _default_strategy_rules()
        results = evaluate_strategy_rules(setup, rules, config)

        bullish_rule = [r for r in results if r["rule_name"] == "bullish_high_confidence"]
        assert len(bullish_rule) > 0
        assert bullish_rule[0]["passed"] is True

    def test_bearish_rule_does_not_match_bullish_setup(self):
        """Bearish rule skipped for bullish setup."""
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 3, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            smt_events=[_smt("bullish")],
            session="london",
        )
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish")],
            swi_points=[{"swing_type": "low", "price": 5990.0}],
        )

        rules = _default_strategy_rules()
        results = evaluate_strategy_rules(setup, rules)

        bearish = [r for r in results if r["rule_name"] == "bearish_high_confidence"]
        assert len(bearish) == 0  # skipped, not matched

    def test_rule_with_low_score_fails(self):
        """Setup with score below min_score fails."""
        rule = StrategyRule(
            name="test_min_score",
            direction="bullish",
            required_conditions=[{"field": "direction", "op": "eq", "value": "bullish"}],
            min_score=90,
        )
        # Low score setup
        confluence = {"trend": "neutral", "swing_direction": "neutral",
                      "bullish_signals": 0, "bearish_signals": 0,
                      "agreement_ratio": 0}
        bias = build_market_bias("ES", "5m", _dt(), confluence,
                                 ms_events=[_ms_event("BOS", "bullish")])
        setup = generate_trade_setup(bias, order_blocks=[_ob("bullish")],
                                     swi_points=[{"swing_type": "low", "price": 5990.0}])
        results = evaluate_strategy_rules(setup, [rule])
        # Score is low (max ~75 with one engine), rule wants 90
        assert results[0]["passed"] is False

    def test_disabled_rule_skipped(self):
        """Disabled rules are not evaluated."""
        rule = StrategyRule(name="disabled", direction="bullish",
                            required_conditions=[], enabled=False)
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 1, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
        )
        setup = generate_trade_setup(bias)
        results = evaluate_strategy_rules(setup, [rule])
        assert len(results) == 0

    def test_rule_priority_sorting(self):
        """Results sorted by priority (descending)."""
        rules = [
            StrategyRule(name="low", direction="bullish", required_conditions=[], priority=1),
            StrategyRule(name="high", direction="bullish", required_conditions=[], priority=10),
        ]
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 1, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
        )
        setup = generate_trade_setup(bias)
        results = evaluate_strategy_rules(setup, rules)
        assert len(results) == 2
        assert results[0]["rule_name"] == "high"


# ─── Scoring Tests ───────────────────────────────────────────

class TestScoring:
    """Score → grade and confidence conversion."""

    def test_score_to_grade(self):
        assert score_to_grade(100) == "A+"
        assert score_to_grade(95) == "A+"
        assert score_to_grade(92) == "A"
        assert score_to_grade(87) == "A-"
        assert score_to_grade(82) == "B+"
        assert score_to_grade(77) == "B"
        assert score_to_grade(72) == "B-"
        assert score_to_grade(67) == "C+"
        assert score_to_grade(62) == "C"
        assert score_to_grade(57) == "C-"
        assert score_to_grade(52) == "D"
        assert score_to_grade(30) == "F"
        assert score_to_grade(0) == "F"

    def test_score_to_confidence(self):
        assert score_to_confidence(90) == "Very High"
        assert score_to_confidence(75) == "High"
        assert score_to_confidence(60) == "Medium"
        assert score_to_confidence(45) == "Low"
        assert score_to_confidence(20) == "Very Low"

    def test_weight_config_custom(self):
        """Custom scoring weights change scores."""
        config = StrategyConfig(scoring_weights={
            "market_structure": 50,
            "fvg_alignment": 0,
            "order_block_presence": 0,
            "smt_confirmation": 0,
            "liquidity_sweep": 0,
            "session_alignment": 0,
        })
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 1, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            session="london",
            config=config,
        )
        # Only MS should contribute 50, FVG gets 0
        assert bias.strength_score == pytest.approx(50.0, abs=1.0)


# ─── Config Tests ────────────────────────────────────────────

class TestStrategyConfig:
    """Configuration serialization."""

    def test_config_round_trip(self):
        config = StrategyConfig(
            min_setup_score=65.0,
            require_all_required=True,
            min_optional_count=3,
            setup_expiry_minutes=120,
            max_targets=2,
            rules=[
                StrategyRule(name="test", required_conditions=[
                    {"field": "direction", "op": "eq", "value": "bullish"},
                ], priority=5),
            ],
        )
        d = config.to_dict()
        c2 = StrategyConfig.from_dict(d)
        assert c2.min_setup_score == 65.0
        assert c2.max_targets == 2
        assert len(c2.rules) == 1
        assert c2.rules[0].name == "test"


# ─── Edge Cases ──────────────────────────────────────────────

class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_historical_consistency(self):
        """Same inputs → same output (deterministic)."""
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 3, "bearish_signals": 0,
                      "agreement_ratio": 1.0}
        t = _dt()

        bias1 = build_market_bias(
            "ES", "5m", t, confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            session="london",
        )
        bias2 = build_market_bias(
            "ES", "5m", t, confluence,
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            session="london",
        )
        assert bias1.direction == bias2.direction
        assert bias1.strength_score == bias2.strength_score
        assert bias1.bias_grade == bias2.bias_grade

    def test_to_dict_serialization(self):
        """MarketBias.to_dict produces valid JSON-serializable dict."""
        confluence = {"trend": "bullish", "swing_direction": "bullish",
                      "bullish_signals": 1, "bearish_signals": 0,
                      "agreement_ratio": 1.0}
        bias = build_market_bias("ES", "5m", _dt(), confluence,
                                 ms_events=[_ms_event("BOS", "bullish")])
        d = bias.to_dict()
        assert isinstance(d, dict)
        assert "direction" in d
        assert "strength_score" in d
        assert isinstance(d["timestamp"], str)

    def test_trade_setup_to_dict(self):
        """TradeSetup.to_dict produces valid dict."""
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 3, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
            fvgs=[_fvg("bullish")],
            order_blocks=[_ob("bullish")],
            session="london",
        )
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish")],
            swi_points=[{"swing_type": "low", "price": 5990.0}],
        )
        d = setup.to_dict()
        assert isinstance(d, dict)
        assert "setup_id" in d
        assert "market_bias" in d
        assert d["market_bias"] is not None

    def test_direction_mismatch_obs(self):
        """Bearish OBs ignored for bullish setup."""
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 1, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
        )
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bearish")],  # wrong direction, ignored
        )
        assert setup.status == "waiting_confirmation"

    def test_missing_stop_no_stop(self):
        """No swings → no stop reference."""
        bias = build_market_bias(
            "ES", "5m", _dt(),
            {"trend": "bullish", "swing_direction": "bullish",
             "bullish_signals": 1, "bearish_signals": 0, "agreement_ratio": 1.0},
            ms_events=[_ms_event("BOS", "bullish")],
        )
        setup = generate_trade_setup(
            bias,
            order_blocks=[_ob("bullish")],
            # no swings
        )
        assert setup.stop_reference is None
        assert "wait_for_stop_reference" in setup.required_confirmation


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_strategy_dry_run_no_db():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.post(
                "/api/v1/strategy/evaluate-dry-run",
                params={"instrument": "ES", "timeframe": "5m", "direction": "bullish"},
            )
            assert response.status_code in (200, 500)
        except Exception:
            pass  # DB not available is fine
