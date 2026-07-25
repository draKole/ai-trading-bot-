# AI Trading Copilot

## Overview
The AI Trading Copilot provides a natural-language advisory interface to the Drake AI Trading platform. It routes user queries to the appropriate services, maintains conversation context, generates structured explanations, and tracks interaction history.

**Architecture**: Advisory only. Never executes trades, never bypasses permissions. All data flows from existing services — the copilot has no trading logic of its own.

## Components

### CopilotController (`services/copilot/engine.py`)
Stateful controller managing the full copilot lifecycle:

| Capability | Description |
|-----------|-------------|
| Intent Routing | Classify natural-language prompts into 12 intents |
| Context Management | Session-scoped context: portfolio, strategy, account, watchlist, time range |
| Query Handling | Route each intent to a domain-specific response method |
| Explanation Engine | Structured explanations referencing originating service(s) |
| Conversation Management | Multi-conversation history per session |
| Suggested Questions | Context-aware question generation |

### Intent Router
Keyword-based deterministic classification into 12 intents:
- portfolio, positions, orders, risk, scanner, optimization
- monitoring, analytics, backtesting, security, system, general

Each intent maps to 2-5 keywords. Unrecognized prompts fall back to `general`.

### Context Manager
Per-session context tracks:
- `portfolio_id`, `strategy_id`, `account_id` — active trading context
- `time_range` — today, 1w, 1m, ytd
- `watchlist_name` — active scanner watchlist
- `optimization_run_id` — current optimization session

### Explanation Engine
Generates human-readable explanations for 7 decision types, each referencing its originating engine(s):

| Decision | Source Engines |
|----------|---------------|
| trade_accept | Strategy, Risk |
| trade_reject | Risk |
| risk_decision | Risk, Portfolio |
| sizing | Position Sizing, Risk |
| allocation | Portfolio |
| ranking | Optimization, Analytics |
| alert | Monitoring |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/copilot/chat` | Process natural-language query |
| POST | `/copilot/sessions` | Create new copilot session |
| GET | `/copilot/sessions/{id}` | Get session details |
| DELETE | `/copilot/sessions/{id}` | End session |
| GET | `/copilot/sessions/{id}/context` | Get session context |
| POST | `/copilot/sessions/{id}/context` | Update session context |
| GET | `/copilot/history/{session_id}` | Get conversation history |
| GET | `/copilot/search` | Search message history |
| POST | `/copilot/feedback` | Submit response feedback |
| GET | `/copilot/feedback/{message_id}` | Get message feedback |
| GET | `/copilot/suggestions` | Get suggested questions |
| GET | `/copilot/system` | Get system context |

## Database Tables

| Table | Purpose |
|-------|---------|
| `copilot_sessions` | Active copilot sessions with context |
| `copilot_conversations` | Conversations within sessions |
| `copilot_messages` | Individual messages with intent/source tracking |
| `copilot_feedback` | User ratings and comments on responses |

## Permission Model

The copilot is advisory-only:
- **Read operations** — all queries available without authentication
- **Context management** — scoped by `user_id`; integrate with Security module for role-based access
- **No trade execution** — intentionally excluded; routes trade-related language to advisory responses
- **No permission bypass** — cannot access data an authenticated user can't see

## Known Limitations

1. **No LLM integration** — keyword-based routing, not actual NLP. In production, replace `classify_intent()` with an LLM call while keeping the same response structure.
2. **Template-based responses** — domain methods return canned text with platform service references. Extend with real API calls to populate live data.
3. **In-memory conversations** — controller stores conversations in dicts. For persistence, use the CopilotService DB layer.
4. **No multi-turn reasoning** — each query is independent. The context manager provides continuity but responses don't reference prior messages.
5. **English only** — keyword matching is English-specific.

## Design Decisions

1. **Deterministic routing**: Intent classification is keyword-based and reproducible — same prompt always produces same intent.
2. **Source attribution**: Every `CopilotResponse` lists `source_services` — the originating engines for the response data.
3. **Advisory guardrails**: Trade-like language is routed to advisory intents, never execution paths.
4. **Context scoping**: Session-level context isolates users; clearing a session resets all tracked state.
