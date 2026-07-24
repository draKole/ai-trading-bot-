# Production Operations & Monitoring

## Overview

Read-only observability platform for system health, alerting, audit logging, and metrics. Observes without modifying trading decisions — never interferes with the pipeline.

## Architecture

```
System Components → MonitoringController → Health Checks
                                          → Metrics
                     AlertManager → Alerts (create/ack/resolve)
                     AuditLogger → Immutable audit trail
                                          ↓
                               Dashboard API (JSON)
```

---

## 1. Health Checks

`MonitoringController` provides 7 endpoint-backed checks:

| Component | Statuses | Conditions |
|-----------|----------|------------|
| `system` | healthy | Always (if running) |
| `database` | healthy/unhealthy | Connection test |
| `broker` | healthy/degraded | Connection state |
| `market_data` | healthy/degraded | Data flow status |
| `live_trading` | healthy/degraded | Active sessions |
| `paper_trading` | healthy | Session count |
| `workers` | healthy/degraded | Worker status |

Aggregated status: unhealthy > degraded > healthy (worst wins).

---

## 2. Alerts

`AlertManager` lifecycle:

```
create → active → acknowledge → acknowledged → resolve → resolved
         ↑ critical/warning/info
```

### Alert Types
broker_disconnected, market_data_disconnected, failed_order, order_timeout, risk_limit_exceeded, daily_loss_limit, high_latency, db_unavailable, engine_failure, missed_heartbeat, excessive_reconnects

### Severity Levels
- **critical**: Requires immediate attention (broker down, kill switch, daily loss)
- **warning**: Degraded but not blocking (latency, disconnected market data)
- **info**: Informational only

---

## 3. Audit Logging

Immutable timestamp-ordered audit trail for:

- Strategy signals (generated, accepted, rejected)
- Risk decisions (approved, vetoed)
- Sizing decisions (recommended, accepted)
- Trade management actions (entered, stopped, exited)
- Broker requests/responses
- Manual operator actions
- Config changes
- Auth events
- System startup/shutdown

---

## 4. Metrics Collection

| Category | Metrics |
|----------|---------|
| Trading | orders/min, avg execution latency, fill latency |
| System | API latency, request rate, error rate, memory/CPU |
| Positions | active sessions, open positions, daily P&L, win rate, drawdown |

Stored historically with tags for aggregation.

---

## 5. API Endpoints

### Health
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/monitoring/health` | Overall status |
| `GET` | `/monitoring/health/system` | System check |
| `GET` | `/monitoring/health/database` | DB check |
| `GET` | `/monitoring/health/broker` | Broker check |
| `GET` | `/monitoring/health/market-data` | Market data |
| `GET` | `/monitoring/health/live-trading` | Live trading |
| `GET` | `/monitoring/health/paper-trading` | Paper trading |
| `GET` | `/monitoring/health/workers` | Workers |
| `POST` | `/monitoring/health/run-all` | Run all + persist |

### Alerts
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/monitoring/alerts` | List with filters |
| `POST` | `/monitoring/alerts/create` | Create |
| `POST` | `/monitoring/alerts/{id}/acknowledge` | Acknowledge |
| `POST` | `/monitoring/alerts/{id}/resolve` | Resolve |

### Audit
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/monitoring/audit-logs` | List with filters |
| `POST` | `/monitoring/audit-logs` | Create entry |

### Metrics
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/monitoring/metrics` | List/aggregate |
| `POST` | `/monitoring/metrics` | Record |

### Other
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/monitoring/dashboard` | Combined data |
| `GET` | `/monitoring/statistics` | Summary stats |

## 6. Database Schema

- `system_health`: component, status, detail, timestamp
- `alerts`: alert_type, severity, message, status, acknowledged_at, resolved_at
- `audit_logs`: event_type, source, entity_type, entity_id, detail_json, operator, timestamp
- `performance_metrics`: name, value, tags_json, timestamp

## 7. Limitations

1. Read-only — cannot modify trading state
2. No WebSocket push — polling only
3. In-memory metrics and alerts — lost on restart without DB persistence
4. No notification channels (email, Slack, SMS)
5. Dashboard data is JSON only — no frontend rendering
