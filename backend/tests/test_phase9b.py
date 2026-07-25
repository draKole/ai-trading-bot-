"""Phase 9B Tests — AI Trading Copilot."""

import json
from datetime import datetime, timezone
import pytest
from app.services.copilot.engine import (
    CopilotController, CopilotResponse, CopilotContext,
    classify_intent, INTENT_KEYWORDS,
)


class TestIntentRouting:
    def test_portfolio_intent(self):
        assert classify_intent("show my portfolio allocation") == "portfolio"
        assert classify_intent("what is my equity") == "portfolio"
        assert classify_intent("how is my capital distributed") == "portfolio"

    def test_positions_intent(self):
        assert classify_intent("show open positions") == "positions"
        assert classify_intent("what is my exposure") == "positions"
        assert classify_intent("list my holdings") == "positions"

    def test_orders_intent(self):
        assert classify_intent("pending orders") == "orders"
        assert classify_intent("show filled orders") == "orders"
        assert classify_intent("order execution status") == "orders"

    def test_risk_intent(self):
        assert classify_intent("what is my risk") == "risk"
        assert classify_intent("show max drawdown") == "risk"
        assert classify_intent("stop loss status") == "risk"

    def test_scanner_intent(self):
        assert classify_intent("scanner opportunities") == "scanner"
        assert classify_intent("scan my watchlist") == "scanner"
        assert classify_intent("any new signals") == "scanner"

    def test_optimization_intent(self):
        assert classify_intent("show optimization results") == "optimization"
        assert classify_intent("walk-forward analysis") == "optimization"
        assert classify_intent("run monte carlo") == "optimization"

    def test_monitoring_intent(self):
        assert classify_intent("system health") == "monitoring"
        assert classify_intent("show active alerts") == "monitoring"
        assert classify_intent("cpu usage") == "monitoring"

    def test_analytics_intent(self):
        assert classify_intent("show sharpe ratio") == "analytics"
        assert classify_intent("what is my sortino") == "analytics"
        assert classify_intent("profit factor") == "analytics"

    def test_backtesting_intent(self):
        assert classify_intent("run backtest") == "backtesting"
        assert classify_intent("historical simulation") == "backtesting"
        assert classify_intent("replay results") == "backtesting"

    def test_system_intent(self):
        assert classify_intent("platform status") == "system"
        assert classify_intent("what version") == "system"
        assert classify_intent("broker connection") == "system"

    def test_general_fallback(self):
        assert classify_intent("hello") == "general"
        assert classify_intent("help me") == "general"
        assert classify_intent("what can you do") == "general"

    def test_empty_string(self):
        assert classify_intent("") == "general"

    def test_mixed_priority(self):
        # "portfolio" and "risk" both match — portfolio has more keyword hits
        result = classify_intent("my portfolio risk and equity allocation")
        assert result == "portfolio"

    def test_deterministic(self):
        for _ in range(10):
            assert classify_intent("show my portfolio allocation") == "portfolio"


class TestContextManagement:
    def test_default_context(self):
        c = CopilotController()
        ctx = c.get_context("s1")
        assert ctx.portfolio_id is None
        assert ctx.time_range == "today"

    def test_set_context(self):
        c = CopilotController()
        c.set_context("s1", portfolio_id=5, time_range="1w")
        ctx = c.get_context("s1")
        assert ctx.portfolio_id == 5
        assert ctx.time_range == "1w"

    def test_clear_context(self):
        c = CopilotController()
        c.set_context("s1", portfolio_id=5)
        assert c.get_context("s1").portfolio_id == 5
        c.clear_context("s1")
        assert c.get_context("s1").portfolio_id is None

    def test_context_to_dict(self):
        ctx = CopilotContext(portfolio_id=1, strategy_id=2, watchlist_name="Futures")
        d = ctx.to_dict()
        assert d["portfolio_id"] == 1
        assert d["strategy_id"] == 2
        assert d["watchlist_name"] == "Futures"

    def test_multiple_sessions_independent(self):
        c = CopilotController()
        c.set_context("s1", portfolio_id=1)
        c.set_context("s2", portfolio_id=2)
        assert c.get_context("s1").portfolio_id == 1
        assert c.get_context("s2").portfolio_id == 2

    def test_metadata_preserved(self):
        ctx = CopilotContext(metadata={"key": "value"})
        assert ctx.metadata["key"] == "value"


class TestQueryHandling:
    def test_handle_portfolio_query(self):
        c = CopilotController()
        resp = c.handle_query("show my portfolio")
        assert resp.intent == "portfolio"
        assert "Portfolio service" in resp.content

    def test_handle_positions_query(self):
        c = CopilotController()
        resp = c.handle_query("open positions")
        assert resp.intent == "positions"
        assert "Live Trading" in resp.content

    def test_handle_risk_query(self):
        c = CopilotController()
        resp = c.handle_query("what is my risk")
        assert resp.intent == "risk"
        assert "Risk Engine" in resp.content

    def test_handle_scanner_query(self):
        c = CopilotController()
        resp = c.handle_query("scan for opportunities")
        assert resp.intent == "scanner"
        assert "Scanner engine" in resp.content

    def test_handle_optimization_query(self):
        c = CopilotController()
        resp = c.handle_query("show optimization runs")
        assert resp.intent == "optimization"
        assert "Optimization engine" in resp.content

    def test_handle_monitoring_query(self):
        c = CopilotController()
        resp = c.handle_query("system health")
        assert resp.intent == "monitoring"
        assert "Monitoring service" in resp.content

    def test_handle_analytics_query(self):
        c = CopilotController()
        resp = c.handle_query("sharpe ratio")
        assert resp.intent == "analytics"
        assert "Analytics engine" in resp.content

    def test_handle_backtesting_query(self):
        c = CopilotController()
        resp = c.handle_query("run backtest strategy")
        assert resp.intent == "backtesting"
        assert "Backtesting engine" in resp.content

    def test_handle_system_query(self):
        c = CopilotController()
        resp = c.handle_query("platform status")
        assert resp.intent == "system"
        assert "Monitoring" in resp.content

    def test_handle_general_query(self):
        c = CopilotController()
        resp = c.handle_query("hello")
        assert resp.intent == "general"
        assert len(resp.suggested_followups) > 0

    def test_response_has_id(self):
        c = CopilotController()
        resp = c.handle_query("portfolio")
        d = resp.to_dict()
        assert "response_id" in d
        assert d["intent"] == "portfolio"

    def test_suggested_followups_present(self):
        c = CopilotController()
        for intent in ["portfolio", "positions", "risk", "scanner", "optimization",
                       "monitoring", "analytics", "backtesting", "system", "general"]:
            resp = c.handle_query(intent)
            assert len(resp.suggested_followups) >= 2, f"No followups for {intent}"


class TestExplanationEngine:
    def test_trade_accept(self):
        c = CopilotController()
        resp = c.explain_decision("trade_accept", {})
        assert "Strategy engine" in resp.content
        assert "Risk Engine" in resp.content
        assert "strategy" in resp.source_services

    def test_trade_reject(self):
        c = CopilotController()
        resp = c.explain_decision("trade_reject", {})
        assert "Risk Engine" in resp.content
        assert "risk" in resp.source_services

    def test_risk_decision(self):
        c = CopilotController()
        resp = c.explain_decision("risk_decision", {})
        assert "Risk Engine" in resp.content
        assert "risk" in resp.source_services
        assert "portfolio" in resp.source_services

    def test_sizing(self):
        c = CopilotController()
        resp = c.explain_decision("sizing", {})
        assert "Position Sizing" in resp.content
        assert "position_sizing" in resp.source_services

    def test_allocation(self):
        c = CopilotController()
        resp = c.explain_decision("allocation", {})
        assert "Portfolio service" in resp.content
        assert "portfolio" in resp.source_services

    def test_ranking(self):
        c = CopilotController()
        resp = c.explain_decision("ranking", {})
        assert "Optimization engine" in resp.content
        assert "optimization" in resp.source_services

    def test_alert(self):
        c = CopilotController()
        resp = c.explain_decision("alert", {})
        assert "Monitoring service" in resp.content
        assert "monitoring" in resp.source_services

    def test_unknown_decision(self):
        c = CopilotController()
        resp = c.explain_decision("unknown_type", {})
        assert resp.content  # still returns something


class TestConversationManagement:
    def test_start_conversation(self):
        c = CopilotController()
        conv = c.start_conversation("s1")
        assert "conversation_id" in conv
        assert conv["session_id"] == "s1"

    def test_add_message(self):
        c = CopilotController()
        conv = c.start_conversation("s1")
        msg = c.add_message("s1", conv["conversation_id"], "user",
                            "Show portfolio", intent="portfolio")
        assert msg["role"] == "user"
        assert msg["intent"] == "portfolio"

    def test_get_conversation(self):
        c = CopilotController()
        conv = c.start_conversation("s1")
        c.add_message("s1", conv["conversation_id"], "user", "Hello")
        retrieved = c.get_conversation("s1", conv["conversation_id"])
        assert retrieved is not None
        assert len(retrieved["messages"]) == 1

    def test_multiple_conversations(self):
        c = CopilotController()
        c.start_conversation("s1")
        c.start_conversation("s1")
        convs = c.get_conversations("s1")
        assert len(convs) == 2

    def test_assistant_response_tracked(self):
        c = CopilotController()
        conv = c.start_conversation("s1")
        c.add_message("s1", conv["conversation_id"], "user", "portfolio")
        c.add_message("s1", conv["conversation_id"], "assistant",
                      "Portfolio summary...", intent="portfolio",
                      source_services=["portfolio"])
        retrieved = c.get_conversation("s1", conv["conversation_id"])
        assert len(retrieved["messages"]) == 2


class TestSuggestedQuestions:
    def test_base_suggestions(self):
        c = CopilotController()
        questions = c.suggested_questions()
        assert len(questions) == 4  # base set
        assert any("portfolio" in q.lower() for q in questions)

    def test_context_aware_suggestions(self):
        c = CopilotController()
        ctx = CopilotContext(watchlist_name="Futures", portfolio_id=1)
        questions = c.suggested_questions(context=ctx)
        assert len(questions) == 6

    def test_max_suggestions(self):
        c = CopilotController()
        ctx = CopilotContext(watchlist_name="Futures", portfolio_id=1)
        questions = c.suggested_questions(context=ctx)
        assert len(questions) <= 6


class TestSystemContext:
    def test_system_context(self):
        c = CopilotController()
        ctx = c.system_context()
        assert "available_intents" in ctx
        assert "advisory_only" in ctx
        assert ctx["advisory_only"] is True
        assert len(ctx["available_intents"]) >= 10


class TestCopilotResponse:
    def test_to_dict(self):
        resp = CopilotResponse(
            response_id="abc", intent="portfolio",
            content="Portfolio data",
            source_services=["portfolio", "live_trading"],
            confidence=0.95,
            suggested_followups=["Show allocation", "Risk summary"],
        )
        d = resp.to_dict()
        assert d["response_id"] == "abc"
        assert d["intent"] == "portfolio"
        assert d["confidence"] == 0.95
        assert d["source_services"] == ["portfolio", "live_trading"]
        assert len(d["suggested_followups"]) == 2

    def test_default_confidence(self):
        resp = CopilotResponse(response_id="x", intent="general", content="Hello")
        d = resp.to_dict()
        assert d["confidence"] == 1.0


class TestSerialization:
    def test_response_serializable(self):
        resp = CopilotResponse(response_id="x", intent="portfolio", content="test")
        json.dumps(resp.to_dict())

    def test_context_serializable(self):
        ctx = CopilotContext(portfolio_id=1)
        json.dumps(ctx.to_dict())

    def test_system_context_serializable(self):
        c = CopilotController()
        json.dumps(c.system_context())


class TestDeterminism:
    def test_intent_routing_deterministic(self):
        for i in range(20):
            assert classify_intent("show my portfolio and risk allocation") == "portfolio"

    def test_handle_query_deterministic(self):
        c1 = CopilotController()
        c2 = CopilotController()
        r1 = c1.handle_query("portfolio")
        r2 = c2.handle_query("portfolio")
        assert r1.intent == r2.intent
        assert r1.content == r2.content
        assert r1.source_services == r2.source_services

    def test_explanation_deterministic(self):
        c1 = CopilotController()
        c2 = CopilotController()
        assert c1.explain_decision("trade_reject", {}).content == \
               c2.explain_decision("trade_reject", {}).content


class TestLargeHistories:
    def test_many_messages(self):
        c = CopilotController()
        conv = c.start_conversation("s1")
        for i in range(200):
            c.add_message("s1", conv["conversation_id"],
                          "user" if i % 2 == 0 else "assistant",
                          f"Message {i}")
        retrieved = c.get_conversation("s1", conv["conversation_id"])
        assert len(retrieved["messages"]) == 200

    def test_many_conversations(self):
        c = CopilotController()
        for i in range(50):
            c.start_conversation("s1")
        convs = c.get_conversations("s1")
        assert len(convs) == 50


class TestConcurrentSessions:
    def test_independent_sessions(self):
        c = CopilotController()
        c.set_context("A", portfolio_id=1)
        c.set_context("B", portfolio_id=2)
        c.set_context("C", portfolio_id=3)
        assert c.get_context("A").portfolio_id == 1
        assert c.get_context("B").portfolio_id == 2
        assert c.get_context("C").portfolio_id == 3

    def test_conversations_per_session(self):
        c = CopilotController()
        c.start_conversation("A")
        c.start_conversation("A")
        c.start_conversation("B")
        assert len(c.get_conversations("A")) == 2
        assert len(c.get_conversations("B")) == 1


class TestPermissions:
    """Copilot is advisory only — no trade execution, no permission bypass."""
    def test_no_trade_execution(self):
        c = CopilotController()
        resp = c.handle_query("buy 10 ES contracts")
        # Should route as general or portfolio, never execute
        assert resp.intent in ["general", "positions"]
        assert "buy" not in resp.content.lower() or "advisory" in resp.content.lower()

    def test_all_reads_no_auth(self):
        c = CopilotController()
        # All queries work without auth context
        for intent in ["portfolio", "positions", "risk", "scanner", "monitoring",
                       "analytics", "backtesting", "system"]:
            resp = c.handle_query(intent)
            assert resp.content

    def test_explanations_no_auth(self):
        c = CopilotController()
        for decision in ["trade_accept", "trade_reject", "risk_decision",
                         "sizing", "allocation", "ranking", "alert"]:
            resp = c.explain_decision(decision, {})
            assert resp.content


class TestServiceAttribution:
    """Every response references originating service(s)."""
    def test_portfolio_sources(self):
        c = CopilotController()
        resp = c.handle_query("portfolio")
        assert len(resp.source_services) > 0

    def test_positions_sources(self):
        c = CopilotController()
        resp = c.handle_query("positions")
        assert len(resp.source_services) > 0

    def test_explanation_sources(self):
        c = CopilotController()
        for decision, expected_sources in [
            ("trade_accept", ["strategy", "risk"]),
            ("trade_reject", ["risk"]),
            ("risk_decision", ["risk", "portfolio"]),
            ("sizing", ["position_sizing", "risk"]),
            ("allocation", ["portfolio"]),
            ("ranking", ["optimization", "analytics"]),
            ("alert", ["monitoring"]),
        ]:
            resp = c.explain_decision(decision, {})
            for src in expected_sources:
                assert src in resp.source_services, f"{decision} missing {src}"


class TestIntentKeywords:
    def test_all_intents_have_keywords(self):
        assert len(INTENT_KEYWORDS) >= 11

    def test_every_intent_matchable(self):
        for intent, keywords in INTENT_KEYWORDS.items():
            # Each intent should match at least its first keyword
            assert classify_intent(keywords[0]) == intent
