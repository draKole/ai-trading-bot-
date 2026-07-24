# Paper Trading Engine — Simulated Execution

## Overview

The Paper Trading Engine executes simulated trades using live market data through the full pipeline. It supports multiple concurrent accounts, market/limit/stop orders, fills with slippage and commission, position tracking, and portfolio analytics. Never duplicates pipeline logic — imports and calls existing engines.

## Architecture

```
Market Data → Pipeline Engines → PaperTradingController
                                      ↓
                              PaperTradingSession (per account)
                              ├── Orders (pending/filled/cancelled)
                              ├── Positions (open/closed)
                              └── Executions (immutable fills)
                                      ↓
                              Statistics & P&L Tracking
```

---

## 1. Session Management

`PaperTradingController` manages multiple concurrent sessions:

| Method | Description |
|--------|-------------|
| `create_session(config)` | Create new paper account |
| `start/pause/resume/stop(account_id)` | Lifecycle control |
| `list_sessions()` | All active sessions |
| `get_session(account_id)` | Single session lookup |

### PaperTradingConfig

| Field | Default | Description |
|-------|---------|-------------|
| `account_id` | UUID | Unique account identifier |
| `name` | "Default" | Display name |
| `initial_balance` | $100,000 | Starting equity |
| `default_slippage_ticks` | 1 | Slippage in ticks |
| `tick_size` | $0.25 | Per-tick value |
| `commission_per_contract` | $2.50 | Per-trade cost |
| `max_positions` | 10 | Position limit |
| `max_risk_per_trade_pct` | 1.0% | Risk cap |

---

## 2. Order Types & Execution

| Order Type | Behavior |
|-----------|----------|
| **Market** | Fills immediately at current price + slippage |
| **Limit** | Fills only if price crosses limit (buy: ≤ limit, sell: ≥ limit). No slippage. |
| **Stop** | Triggers market order when stop price is reached |
| **Stop-Limit** | Triggers limit order when stop price is reached |

### Slippage Model
- Buy orders: fill_price = current_price + (ticks × tick_size)
- Sell orders: fill_price = current_price − (ticks × tick_size)
- Limit orders: zero slippage (fill at limit or better)

### Commission
`commission = quantity × commission_per_contract`

---

## 3. Position Management

- **Long positions**: created on buy, reduced on sell
- **Short positions**: created on sell, reduced on buy
- **Partial exits**: supported — position size reduced proportionally
- **P&L tracking**: realized on close, unrealized mark-to-market
- **Position flipping**: selling more than owned flips to net short

---

## 4. Portfolio Analytics

`get_statistics()` returns:
- Balance, buying power, realized/unrealized P&L
- Total P&L (realized + unrealized)
- Open/closed position counts
- Win rate from closed positions
- Order and execution counts

---

## 5. State Recovery

`export_state()` / `import_state()` enable session persistence and recovery after restart. Exports all session data, orders, positions, and executions as serializable dicts.

---

## 6. Database Schema

### `paper_trading_sessions` — 13 columns
id, account_id (unique), name, balance, buying_power, initial_balance, realized_pnl, unrealized_pnl, status, config_json, started_at, stopped_at, created_at.

Indexes: account_id, status.

### `paper_orders` — 16 columns
id, session_id FK, order_type, side, instrument, quantity, price, stop_price, status, filled_qty, fill_price, slippage, commission, expiry, cancelled_at, created_at.

Indexes: session_id, status.

### `paper_positions` — 13 columns
id, session_id FK, instrument, direction, quantity, avg_entry_price, current_price, unrealized_pnl, realized_pnl, status, opened_at, closed_at, created_at.

Indexes: session_id, status.

### `paper_executions` — 10 columns
id, session_id FK, order_id FK, instrument, side, quantity, price, commission, slippage, created_at.

Indexes: session_id, order_id.

---

## 7. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/paper/sessions` | List sessions |
| `GET` | `/api/v1/paper/sessions/{id}` | Get session |
| `POST` | `/api/v1/paper/start` | Create + start |
| `POST` | `/api/v1/paper/sessions/{id}/stop` | Stop |
| `POST` | `/api/v1/paper/sessions/{id}/pause` | Pause |
| `POST` | `/api/v1/paper/sessions/{id}/resume` | Resume |
| `POST` | `/api/v1/paper/orders` | Place order |
| `GET` | `/api/v1/paper/orders` | List orders |
| `GET` | `/api/v1/paper/positions` | List positions |
| `GET` | `/api/v1/paper/executions` | List executions |
| `GET` | `/api/v1/paper/statistics` | Session stats |

---

## 8. Limitations

1. No broker integration — simulated fills only
2. Stop and stop-limit order types defined but not fully implemented
3. No partial fills — orders are all-or-nothing
4. In-memory controller — session state lost on restart without explicit state export/import
5. No multi-instrument portfolio margining
6. Position mark-to-market requires manual price updates
