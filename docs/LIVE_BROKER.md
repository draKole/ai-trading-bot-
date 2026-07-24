# Live Broker Integration — Abstract Adapter & Live Trading Engine

## Overview

The Broker Adapter Layer provides a standardized interface for connecting to live brokers. The Live Trading Engine orchestrates real trade execution through the full pipeline with safety controls. Only the BrokerAdapter talks to external APIs — never pipeline code.

## Architecture

```
Pipeline Signal → SafetyController → LiveTradingController → BrokerAdapter (Tradovate)
                    (limits/kill)       (orchestrator)         (external API)
                                              ↓
                                    LiveTradingSession
                                    ├── Orders (pending/filled)
                                    ├── Positions (sync'd)
                                    └── Executions (fills)
```

---

## 1. Broker Adapter Interface (`BrokerAdapter`)

Abstract base class that all broker implementations MUST implement:

| Method | Returns | Purpose |
|--------|---------|---------|
| `connect()` | `bool` | Establish broker connection |
| `disconnect()` | `bool` | Tear down connection |
| `is_connected()` | `bool` | Connection status |
| `place_order(order)` | `BrokerOrder` | Submit order, returns updated order |
| `modify_order(id, updates)` | `BrokerOrder` | Modify existing order |
| `cancel_order(id)` | `bool` | Cancel order |
| `get_order(id)` | `BrokerOrder` | Get order status |
| `get_positions()` | `list[BrokerPosition]` | Current positions |
| `get_account()` | `BrokerAccount` | Account info |
| `get_account_summary()` | `dict` | Convenience wrapper |
| `get_market_price(instrument)` | `float` | Current market price |

### Events
`register_callback(callback)` — receive `BrokerEvent` objects for:
- `order_accepted`, `partial_fill`, `full_fill`
- `cancelled`, `rejected`, `modified`
- `position_update`, `connection_lost`, `reconnected`
- `heartbeat`

---

## 2. Tradovate Adapter

Simulated implementation for testing. In production, would connect to Tradovate's REST/WebSocket API.

- Market orders: fill immediately at default price
- Limit orders: placed but not auto-filled (requires price crossing)
- Connection management: connect → heartbeat → disconnect
- Position tracking: tracks buy/sell fills, computes average entry

---

## 3. Live Trading Controller

Orchestrates live trading with safety:

| Method | Purpose |
|--------|---------|
| `create_session(config, adapter)` | Create live session |
| `connect/disconnect(account_id)` | Broker lifecycle |
| `place_order(account_id, order)` | Route with safety checks |
| `cancel_order(account_id, order_id)` | Cancel through broker |
| `sync_positions/sync_account(account_id)` | Sync from broker |
| `emergency_stop(account_id)` | Kill switch |

### LiveTradingConfig

| Field | Default | Description |
|-------|---------|-------------|
| `max_daily_loss` | $1,000 | Daily loss limit |
| `max_open_positions` | 5 | Position cap |
| `max_account_risk_pct` | 3% | Account risk cap |
| `heartbeat_timeout_seconds` | 60 | Connection monitor |
| `auto_reconnect` | true | Auto-reconnect on loss |
| `halt_on_connection_loss` | true | Stop trading on disconnect |
| `duplicate_order_prevention` | true | Reject duplicate order IDs |

---

## 4. Safety Controller

Validates every order before it reaches the broker:

- Kill switch: halt all trading immediately
- Max positions: reject if at limit
- Duplicate prevention: reject repeated order IDs
- Daily loss limit: reject if exceeded
- Connection check: reject if disconnected

---

## 5. Database Schema

### `live_trading_sessions` — 13 columns
account_id (unique), broker, connection_state, balance, buying_power, initial_balance, realized_pnl, unrealized_pnl, config_json, started_at, stopped_at.

### `live_orders` — 16 columns
session_id FK, broker_order_id, order_type, action, instrument, quantity, limit_price, stop_price, status, filled_qty, avg_fill_price, rejected_reason.

### `live_executions` — 9 columns
session_id FK, order_id FK, instrument, action, quantity, price, commission.

### `broker_connection_logs` — 4 columns
session_id FK, event_type, detail, timestamp.

---

## 6. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/live/sessions` | List sessions |
| `GET` | `/api/v1/live/sessions/{id}` | Get session |
| `POST` | `/api/v1/live/connect` | Connect to broker |
| `POST` | `/api/v1/live/disconnect` | Disconnect |
| `POST` | `/api/v1/live/start` | Create + connect + start |
| `POST` | `/api/v1/live/stop` | Disconnect + stop |
| `GET` | `/api/v1/live/status` | Session status |
| `POST` | `/api/v1/live/orders/place` | Place order |
| `GET` | `/api/v1/live/orders` | List orders |
| `GET` | `/api/v1/live/executions` | List executions |
| `GET` | `/api/v1/live/positions` | Sync + list positions |
| `GET` | `/api/v1/live/account` | Sync + get account |
| `POST` | `/api/v1/live/emergency_stop` | Kill switch |
| `GET` | `/api/v1/live/statistics` | Session stats |

---

## 7. Limitations

1. Tradovate adapter is simulated — no real API connection
2. Heartbeat uses asyncio tasks, not WebSocket
3. No transaction cost modeling beyond commission
4. Position reconciliation is basic (no version tracking)
5. Single broker per session
