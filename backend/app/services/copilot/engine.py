"""AI Trading Copilot Engine — advisory natural-language interface to the platform."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


# --- Intent Registry ---
INTENT_KEYWORDS = {
    "portfolio": ["portfolio", "account", "allocation", "equity", "capital"],
    "positions": ["position", "open trade", "exposure", "holding"],
    "orders": ["order", "pending", "filled", "execution", "entry"],
    "risk": ["risk", "drawdown", "max loss", "var", "stop loss"],
    "scanner": ["scanner", "opportunit", "watchlist", "signal", "scan"],
    "optimization": ["optimiz", "walk-forward", "monte carlo", "parameter", "grid search"],
    "monitoring": ["health", "alert", "latency", "uptime", "cpu", "memory"],
    "analytics": ["sharpe", "sortino", "calmar", "profit factor", "win rate", "analytics"],
    "backtesting": ["backtest", "historical", "replay", "simulation"],
    "security": ["login", "auth", "permission", "api key", "session"],
    "system": ["status", "version", "environment", "broker connect"],
    "general": ["help", "overview", "summary", "dashboard"],
}


def classify_intent(prompt: str) -> str:
    """Classify user prompt into one of the registered intents. Deterministic."""
    lower = prompt.lower()
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[intent] = score
    if not scores:
        return "general"
    return max(scores, key=scores.get)


# --- Data Types ---

@dataclass
class CopilotResponse:
    response_id: str
    intent: str
    content: str
    source_services: list[str] = field(default_factory=list)
    confidence: float = 1.0
    suggested_followups: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "response_id": self.response_id,
            "intent": self.intent,
            "content": self.content,
            "source_services": self.source_services,
            "confidence": round(self.confidence, 2),
            "suggested_followups": self.suggested_followups,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CopilotContext:
    portfolio_id: int | None = None
    strategy_id: int | None = None
    account_id: int | None = None
    time_range: str = "today"
    watchlist_name: str | None = None
    optimization_run_id: int | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "portfolio_id": self.portfolio_id,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "time_range": self.time_range,
            "watchlist_name": self.watchlist_name,
            "optimization_run_id": self.optimization_run_id,
        }


class CopilotController:
    """Advisory-only natural language interface. Routes intents, maintains context,
    generates explanations, and aggregates platform data. Never executes trades."""

    def __init__(self):
        self._contexts: dict[str, CopilotContext] = {}
        self._conversations: dict[str, list[dict]] = {}

    # --- Context Management ---

    def get_context(self, session_id: str) -> CopilotContext:
        if session_id not in self._contexts:
            self._contexts[session_id] = CopilotContext()
        return self._contexts[session_id]

    def set_context(self, session_id: str, **kwargs):
        ctx = self.get_context(session_id)
        for k, v in kwargs.items():
            if hasattr(ctx, k):
                setattr(ctx, k, v)

    def clear_context(self, session_id: str):
        self._contexts.pop(session_id, None)

    # --- Intent Routing ---

    def route(self, prompt: str) -> str:
        """Classify intent from natural-language prompt."""
        return classify_intent(prompt)

    # --- Query Handling ---

    def handle_query(self, prompt: str, session_id: str | None = None,
                     context: CopilotContext | None = None) -> CopilotResponse:
        """Process a natural-language query and return structured response."""
        intent = self.route(prompt)
        ctx = context or (self.get_context(session_id) if session_id else CopilotContext())

        if intent == "portfolio":
            return self._portfolio_response(prompt, ctx)
        elif intent == "positions":
            return self._positions_response(prompt, ctx)
        elif intent == "risk":
            return self._risk_response(prompt, ctx)
        elif intent == "scanner":
            return self._scanner_response(prompt, ctx)
        elif intent == "optimization":
            return self._optimization_response(prompt, ctx)
        elif intent == "monitoring":
            return self._monitoring_response(prompt, ctx)
        elif intent == "analytics":
            return self._analytics_response(prompt, ctx)
        elif intent == "backtesting":
            return self._backtesting_response(prompt, ctx)
        elif intent == "system":
            return self._system_response(prompt, ctx)
        else:
            return self._general_response(prompt, ctx)

    # --- Domain Response Methods ---

    def _portfolio_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="portfolio",
            content="Portfolio data would be retrieved from the Portfolio service. "
                     f"Active context: portfolio_id={ctx.portfolio_id}, time_range={ctx.time_range}.",
            source_services=["portfolio", "live_trading"],
            suggested_followups=[
                "Show me my current allocation",
                "What is my total equity?",
                "How is my portfolio risk?",
            ],
        )

    def _positions_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="positions",
            content="Position data would be retrieved from Paper Trading / Live Trading services.",
            source_services=["paper_trading", "live_trading"],
            suggested_followups=[
                "Show me my open positions",
                "What is my total P&L?",
                "Are there any at-risk positions?",
            ],
        )

    def _risk_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="risk",
            content="Risk assessment originates from the Risk Engine. "
                     "Portfolio-level risk from Portfolio service. "
                     "Individual trade risk is computed by Risk Engine per setup.",
            source_services=["risk", "portfolio", "trade_management"],
            suggested_followups=[
                "What is my current risk utilization?",
                "Show me risk limits",
                "Any breached risk rules?",
            ],
        )

    def _scanner_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="scanner",
            content="Scanner opportunities originate from the Scanner engine. "
                     f"Active watchlist: {ctx.watchlist_name or 'none set'}.",
            source_services=["scanner", "market_data"],
            suggested_followups=[
                "Show top opportunities",
                "Scan my watchlist",
                "What symbols have high confidence?",
            ],
        )

    def _optimization_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="optimization",
            content="Optimization results come from the Optimization engine (grid search, random search, "
                     "walk-forward, Monte Carlo). Strategy rankings are derived from Analytics metrics.",
            source_services=["optimization", "analytics", "backtesting"],
            suggested_followups=[
                "Show recent optimization runs",
                "What are the best parameters?",
                "Run walk-forward analysis",
            ],
        )

    def _monitoring_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="monitoring",
            content="Platform health is monitored by the Monitoring service (health checks, alerts, "
                     "audit logs, performance metrics). Broker status from Live Trading.",
            source_services=["monitoring", "live_trading"],
            suggested_followups=[
                "System health check",
                "Show active alerts",
                "Broker connectivity status",
            ],
        )

    def _analytics_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="analytics",
            content="Performance analytics (Sharpe, Sortino, Calmar, drawdowns, rolling metrics) "
                     "are computed by the Analytics engine from backtest data.",
            source_services=["analytics", "backtesting"],
            suggested_followups=[
                "Show my Sharpe ratio",
                "What is my maximum drawdown?",
                "Compare strategies",
            ],
        )

    def _backtesting_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="backtesting",
            content="Backtesting executes strategies against historical data via the Backtesting engine. "
                     "Replay engine provides bar-by-bar simulation with no-lookahead enforcement.",
            source_services=["backtesting", "replay", "market_data"],
            suggested_followups=[
                "Run a backtest",
                "Show backtest history",
                "What timeframes are available?",
            ],
        )

    def _system_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="system",
            content="Platform status aggregated from Monitoring, Infrastructure, and Live Trading services.",
            source_services=["monitoring", "infrastructure", "live_trading"],
            suggested_followups=[
                "System health check",
                "What version is running?",
                "Show broker connection status",
            ],
        )

    def _general_response(self, prompt: str, ctx: CopilotContext) -> CopilotResponse:
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="general",
            content="I can help with: portfolio, positions, risk, scanner, optimization, "
                     "monitoring, analytics, backtesting, system status, and security. "
                     "What would you like to know?",
            source_services=[],
            suggested_followups=[
                "Show me my portfolio summary",
                "Any active alerts?",
                "What are today's top opportunities?",
            ],
        )

    # --- Explanation Engine ---

    def explain_decision(self, decision_type: str, decision_data: dict) -> CopilotResponse:
        """Generate structured explanation referencing originating engine(s)."""
        explanations = {
            "trade_accept": "Trade was accepted by Strategy engine based on confluence score. "
                            "Risk Engine verified position is within limits.",
            "trade_reject": "Trade was rejected by Risk Engine. "
                            "Check: max drawdown, daily loss limit, or position exposure limits.",
            "risk_decision": "Risk decision from Risk Engine. Individual trade risk is single source of truth. "
                             "Portfolio-level risk from Portfolio service.",
            "sizing": "Position sizing computed by Position Sizing engine based on account equity "
                      "and Risk Engine parameters.",
            "allocation": "Capital allocation determined by Portfolio service using configured allocation method.",
            "ranking": "Strategy ranking produced by Optimization engine comparing net profit, Sharpe, "
                       "Sortino, Calmar, profit factor, win rate, drawdown, expectancy, recovery factor.",
            "alert": "Alert triggered by Monitoring service based on configured thresholds.",
        }
        text = explanations.get(decision_type,
                                f"No explanation template for '{decision_type}'. "
                                "Refer to originating service documentation.")
        return CopilotResponse(
            response_id=str(uuid4()),
            intent="explanation",
            content=text,
            source_services=self._source_for_decision(decision_type),
        )

    def _source_for_decision(self, decision_type: str) -> list[str]:
        mapping = {
            "trade_accept": ["strategy", "risk"],
            "trade_reject": ["risk"],
            "risk_decision": ["risk", "portfolio"],
            "sizing": ["position_sizing", "risk"],
            "allocation": ["portfolio"],
            "ranking": ["optimization", "analytics"],
            "alert": ["monitoring"],
        }
        return mapping.get(decision_type, [])

    # --- Conversation Management ---

    def start_conversation(self, session_id: str) -> dict:
        conv_id = str(uuid4())
        if session_id not in self._conversations:
            self._conversations[session_id] = []
        conv = {"conversation_id": conv_id, "session_id": session_id,
                "messages": [], "created_at": datetime.now(timezone.utc).isoformat()}
        self._conversations[session_id].append(conv)
        return conv

    def add_message(self, session_id: str, conversation_id: str,
                    role: str, content: str, intent: str = "",
                    source_services: list[str] | None = None) -> dict:
        msg = {
            "message_id": str(uuid4()),
            "role": role,
            "content": content,
            "intent": intent,
            "source_services": source_services or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for conv in self._conversations.get(session_id, []):
            if conv["conversation_id"] == conversation_id:
                conv["messages"].append(msg)
                return msg
        return msg

    def get_conversation(self, session_id: str, conversation_id: str) -> dict | None:
        for conv in self._conversations.get(session_id, []):
            if conv["conversation_id"] == conversation_id:
                return conv
        return None

    def get_conversations(self, session_id: str) -> list[dict]:
        return self._conversations.get(session_id, [])

    # --- Suggested Questions ---

    def suggested_questions(self, context: CopilotContext | None = None) -> list[str]:
        """Generate context-aware suggested questions."""
        base = [
            "How is my portfolio performing today?",
            "Show me open positions",
            "Any active alerts?",
            "System health check",
        ]
        if context and context.watchlist_name:
            base.insert(0, f"Scan {context.watchlist_name} for opportunities")
        if context and context.portfolio_id:
            base.insert(0, "Show portfolio allocation")
        return base[:6]

    # --- System Context ---

    def system_context(self) -> dict:
        """Return available platform context for the copilot."""
        return {
            "available_intents": list(INTENT_KEYWORDS.keys()),
            "available_domains": [
                "portfolio", "positions", "orders", "risk", "scanner",
                "optimization", "monitoring", "analytics", "backtesting",
                "security", "system",
            ],
            "advisory_only": True,
            "version": "1.0.0",
        }
