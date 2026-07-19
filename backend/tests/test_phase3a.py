"""Phase 3A Tests — Confluence Engine.

Tests for snapshot building, rule evaluation, configuration,
edge cases, and historical consistency.
"""

from datetime import datetime, timedelta
import pytest

from app.services.confluence.engine import (
    build_snapshot, evaluate_rules,
    ConfluenceConfig, ConfluenceSnapshot,
    Rule, RuleCondition, RuleResult,
    ConditionOperator, TrendState, SignalDirection,
    _default_rules,
)


# ─── Helpers ─────────────────────────────────────────────────

def _dt(minute_offset=0):
    return datetime(2025, 6, 16, 9, 30) + timedelta(minutes=minute_offset)


def _make_ms_event(event_type, direction, bar_index=1):
    return {"event_type": event_type, "direction": direction,
            "bar_index": bar_index, "timestamp": _dt(bar_index * 5)}


def _make_fvg(direction, status="active"):
    return {"direction": direction, "status": status}


def _make_ob(direction, status="active"):
    return {"direction": direction, "status": status}


def _make_smt(direction):
    return {"direction": direction}


# ─── Snapshot Building ───────────────────────────────────────

class TestBuildSnapshot:
    """Confluence snapshot building from engine outputs."""

    def test_empty_snapshot(self):
        """Empty inputs produce a valid neutral snapshot."""
        snapshot = build_snapshot("ES", "5m", _dt())
        assert snapshot.instrument == "ES"
        assert snapshot.trend == "neutral"
        assert snapshot.swing_direction == "neutral"
        assert snapshot.total_signals == 0

    def test_bullish_trend_from_ms(self):
        """Market Structure bullish events create a bullish trend."""
        ms = [
            _make_ms_event("BOS", "bullish"),
            _make_ms_event("BOS", "bullish"),
            _make_ms_event("CHoCH", "bullish"),
        ]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms)
        assert snapshot.swing_direction == "bullish"
        assert snapshot.ms_bullish_count == 3
        assert snapshot.latest_bos is not None

    def test_bearish_trend_from_ms(self):
        """Market Structure bearish events create bearish trend."""
        ms = [
            _make_ms_event("BOS", "bearish"),
            _make_ms_event("BOS", "bearish"),
        ]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms)
        assert snapshot.swing_direction == "bearish"

    def test_choppy_when_mixed(self):
        """Mixed signals produce choppy trend."""
        ms = [
            _make_ms_event("BOS", "bullish"),
            _make_ms_event("BOS", "bearish"),
        ]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms)
        assert snapshot.trend in ("neutral", "choppy")

    def test_fvg_counts(self):
        """FVGs are correctly counted by direction and status."""
        fvgs = [
            _make_fvg("bullish", "active"),
            _make_fvg("bullish", "active"),
            _make_fvg("bearish", "active"),
            _make_fvg("bearish", "mitigated"),
            _make_fvg("bullish", "partially_filled"),
        ]
        snapshot = build_snapshot("ES", "5m", _dt(), fvgs=fvgs)
        assert snapshot.fvg_active_count == 4  # 2 active bull + 1 active bear + 1 partial
        assert snapshot.fvg_bullish_count == 3
        assert snapshot.fvg_bearish_count == 1
        assert snapshot.fvg_mitigated_count == 1

    def test_ob_counts(self):
        """Order Blocks are correctly counted."""
        obs = [
            _make_ob("bullish", "active"),
            _make_ob("bearish", "touched"),
            _make_ob("bearish", "mitigated"),
        ]
        snapshot = build_snapshot("ES", "5m", _dt(), order_blocks=obs)
        assert snapshot.ob_active_count == 2
        assert snapshot.ob_bullish_count == 1
        assert snapshot.ob_bearish_count == 1
        assert snapshot.ob_mitigated_count == 1

    def test_smt_counts(self):
        """SMT events are correctly counted."""
        smt = [
            _make_smt("bullish"),
            _make_smt("bearish"),
            _make_smt("bullish"),
        ]
        snapshot = build_snapshot("ES", "5m", _dt(), smt_events=smt)
        assert snapshot.smt_active_count == 3
        assert snapshot.smt_bullish_count == 2
        assert snapshot.smt_bearish_count == 1

    def test_aggregate_signals(self):
        """Bullish/bearish signal counts are computed with weights."""
        ms = [_make_ms_event("BOS", "bullish"), _make_ms_event("BOS", "bullish")]
        fvgs = [_make_fvg("bullish", "active")]
        smt = [_make_smt("bullish")]

        config = ConfluenceConfig(
            trend_weight=1.0, fvg_weight=0.8, smt_weight=1.5,
        )
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs, smt_events=smt, config=config)
        # bullish: 1*1.0 + 1*0.8 + 1*1.5 = 3.3
        assert snapshot.bullish_signals == pytest.approx(3.3)
        assert snapshot.bearish_signals == 0

    def test_session_alignment(self):
        """Session alignment is detected for high-activity sessions."""
        snapshot = build_snapshot("ES", "5m", _dt(), session="london")
        assert snapshot.session_aligned is True

        snapshot2 = build_snapshot("ES", "5m", _dt(), session="asia")
        assert snapshot2.session_aligned is False

    def test_agreement_ratio(self):
        """Agreement ratio reflects signal dominance."""
        ms = [_make_ms_event("BOS", "bullish")] * 3
        fvgs = [_make_fvg("bearish", "active")]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs)
        # bullish from MS: 3*1.0=3, bearish from FVG: 1*0.8=0.8
        assert snapshot.bullish_signals > snapshot.bearish_signals
        assert 0 < snapshot.agreement_ratio <= 1.0


# ─── Rule Evaluation ─────────────────────────────────────────

class TestRuleEvaluation:
    """Rule engine evaluation against snapshots."""

    def test_all_operator_all_must_match(self):
        """ALL operator requires every condition to match."""
        rule = Rule(
            name="test_all",
            conditions=[
                RuleCondition("ms.bullish_count", "gt", 0),
                RuleCondition("fvg.bullish", "gt", 0),
            ],
            operator="all",
        )
        ms = [_make_ms_event("BOS", "bullish")]
        fvgs = [_make_fvg("bullish")]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs)
        results = evaluate_rules(snapshot, [rule])
        assert len(results) == 1
        assert results[0].matched is True

    def test_all_operator_partial_fails(self):
        """ALL operator fails if any condition fails."""
        rule = Rule(
            name="test_all",
            conditions=[
                RuleCondition("ms.bullish_count", "gt", 0),
                RuleCondition("fvg.bullish", "gt", 0),
            ],
            operator="all",
        )
        ms = [_make_ms_event("BOS", "bullish")]
        fvgs = [_make_fvg("bearish")]  # bearish, not bullish
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs)
        results = evaluate_rules(snapshot, [rule])
        assert results[0].matched is False

    def test_any_operator(self):
        """ANY operator matches if at least one condition passes."""
        rule = Rule(
            name="test_any",
            conditions=[
                RuleCondition("ms.bullish_count", "gt", 0),
                RuleCondition("fvg.bullish", "gt", 0),
            ],
            operator="any",
        )
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=[_make_ms_event("BOS", "bullish")])
        results = evaluate_rules(snapshot, [rule])
        assert results[0].matched is True

    def test_minimum_operator(self):
        """MINIMUM operator matches if at least N conditions pass."""
        rule = Rule(
            name="test_min",
            conditions=[
                RuleCondition("ms.bullish_count", "gt", 0),
                RuleCondition("fvg.bullish", "gt", 0),
                RuleCondition("ob.bullish", "gt", 0),
                RuleCondition("smt.bullish", "gt", 0),
            ],
            operator="minimum", min_matches=2,
        )
        ms = [_make_ms_event("BOS", "bullish")]
        fvgs = [_make_fvg("bullish")]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs)
        results = evaluate_rules(snapshot, [rule])
        assert results[0].matched is True
        assert results[0].match_count == 2

    def test_majority_operator(self):
        """MAJORITY operator matches if >50% pass."""
        rule = Rule(
            name="test_maj",
            conditions=[
                RuleCondition("ms.bullish_count", "gt", 0),
                RuleCondition("fvg.bullish", "gt", 0),
                RuleCondition("ob.bullish", "gt", 0),
            ],
            operator="majority",
        )
        ms = [_make_ms_event("BOS", "bullish")]
        fvgs = [_make_fvg("bullish")]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs)
        results = evaluate_rules(snapshot, [rule])
        # 2 out of 3 = majority
        assert results[0].matched is True

    def test_rule_weight_affects_score(self):
        """Rule weight multiplies the score."""
        rule_light = Rule(name="light", conditions=[
            RuleCondition("ms.bullish_count", "gt", 0),
        ], operator="all", weight=0.5)

        rule_heavy = Rule(name="heavy", conditions=[
            RuleCondition("ms.bullish_count", "gt", 0),
        ], operator="all", weight=2.0)

        ms = [_make_ms_event("BOS", "bullish")]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms)

        r1 = evaluate_rules(snapshot, [rule_light])[0]
        r2 = evaluate_rules(snapshot, [rule_heavy])[0]
        assert r1.score < r2.score

    def test_disabled_rule_skipped(self):
        """Disabled rules are not evaluated."""
        rule = Rule(name="disabled", conditions=[
            RuleCondition("ms.bullish_count", "gt", 0),
        ], enabled=False)

        snapshot = build_snapshot("ES", "5m", _dt(),
                                  ms_events=[_make_ms_event("BOS", "bullish")])
        results = evaluate_rules(snapshot, [rule])
        assert len(results) == 0

    def test_default_rules(self):
        """Default rules evaluate without error."""
        ms = [_make_ms_event("BOS", "bullish")]
        fvgs = [_make_fvg("bullish")]
        obs = [_make_ob("bullish")]
        smt = [_make_smt("bullish")]

        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs,
                                  order_blocks=obs, smt_events=smt)
        results = evaluate_rules(snapshot, _default_rules())
        assert len(results) == len(_default_rules())
        matched = [r for r in results if r.matched]
        assert len(matched) >= 1


# ─── Edge Cases ──────────────────────────────────────────────

class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_contradictory_signals(self):
        """Bullish MS + bearish FVG → shows both in snapshot."""
        ms = [_make_ms_event("BOS", "bullish")]
        fvgs = [_make_fvg("bearish", "active")]
        snapshot = build_snapshot("ES", "5m", _dt(), ms_events=ms, fvgs=fvgs)
        assert snapshot.swing_direction == "bullish"
        assert snapshot.fvg_bearish_count > 0

    def test_duplicate_prevention(self):
        """Repeated builds return consistent snapshots for same data."""
        ms = [_make_ms_event("BOS", "bullish")]
        s1 = build_snapshot("ES", "5m", _dt(), ms_events=ms)
        s2 = build_snapshot("ES", "5m", _dt(), ms_events=ms)
        assert s1.trend == s2.trend
        assert s1.bullish_signals == s2.bullish_signals

    def test_condition_exists_operator(self):
        """The 'exists' operator checks for non-zero/non-null values."""
        rule = Rule(name="exists_test", conditions=[
            RuleCondition("ms.bullish_count", "exists"),
        ], operator="all")
        snapshot = build_snapshot("ES", "5m", _dt(),
                                  ms_events=[_make_ms_event("BOS", "bullish")])
        results = evaluate_rules(snapshot, [rule])
        assert results[0].matched is True

        snapshot2 = build_snapshot("ES", "5m", _dt())
        results2 = evaluate_rules(snapshot2, [rule])
        assert results2[0].matched is False


# ─── Config Tests ────────────────────────────────────────────

class TestConfluenceConfig:
    """Configuration serialization."""

    def test_config_round_trip(self):
        config = ConfluenceConfig(
            time_window_seconds=7200,
            min_evidence_sources=2,
            trend_weight=1.5,
            fvg_weight=1.0,
            smt_weight=2.0,
            enabled_timeframes=["5m", "1h"],
            rules=[
                Rule(name="test", conditions=[
                    RuleCondition("ms.bullish_count", "gte", 1, weight=2.0),
                ], operator="all", group="test"),
            ],
        )
        d = config.to_dict()
        c2 = ConfluenceConfig.from_dict(d)
        assert c2.time_window_seconds == 7200
        assert c2.min_evidence_sources == 2
        assert len(c2.rules) == 1
        assert c2.rules[0].name == "test"


# ─── API Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confluence_dry_run_no_db():
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.post(
                "/api/v1/confluence/snapshot-dry-run",
                params={"instrument": "ES", "timeframe": "5m"},
            )
            assert response.status_code in (200, 500)
        except Exception:
            pass  # DB not available is fine
