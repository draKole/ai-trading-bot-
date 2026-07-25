# Operator Dashboard & Command Center

## Overview
The Operator Dashboard provides read-only visibility across the entire Drake AI Trading platform. It aggregates state from all subsystems into a unified command center — widgets, statistics, timeline, and full snapshots.

**Architecture**: Read-only orchestration layer. All data flows from existing services/engines — the dashboard never duplicates logic, executes trades, or modifies platform state.

## Components

### DashboardController (`services/dashboard/engine.py`)
Pure aggregation class with no external dependencies. Accepts data as parameters and returns structured dicts:

| Method | Purpose |
|--------|---------|
| `system_overview()` | Platform health, broker status, alerts, uptime, version, session |
| `trading_overview()` | Open positions, orders, daily/unrealized P&L, risk, exposure |
| `scanner_dashboard()` | Active opportunities, watchlist counts, recent scans, avg confidence |
| `optimization_dashboard()` | Recent runs, walk-forward, Monte Carlo, top strategies, best params |
| `monitoring_dashboard()` | Health checks, active alerts, API latency, metrics |
| `portfolio_dashboard()` | Portfolio/account counts, equity, allocation methods, exposure |
| `activity_timeline()` | Unified chronological feed from heterogeneous event sources |
| `snapshot()` | Full platform state capture at a point in time |
| `statistics()` | Aggregate dashboard-level statistics from a snapshot |
| `build_widgets()` | Generate default widget objects from a snapshot |

### Data Types

**TimelineEvent** — timestamped event with type, source, severity, metadata:
```python
@dataclass
class TimelineEvent:
    event_id: str
    event_type: str      # trade, alert, portfolio, optimization, scanner, broker, auth, system
    source: str
    summary: str
    severity: str = "info"  # info, warning, critical
    metadata: dict = field(default_factory=dict)
    timestamp: datetime    # timezone-aware UTC
```

**WidgetData** — dashboard widget definition:
```python
@dataclass
class WidgetData:
    widget_id: str
    widget_type: str      # system, trading, portfolio, monitoring, scanner, optimization, timeline
    title: str
    data: dict
    refresh_interval_s: int = 30
```

## API Endpoints

### Snapshot
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/snapshot` | Generate live platform snapshot |
| POST | `/dashboard/snapshot` | Persist current snapshot |
| GET | `/dashboard/snapshot/history` | List saved snapshots (filter by type) |
| GET | `/dashboard/snapshot/{id}` | Get specific snapshot |
| DELETE | `/dashboard/snapshot/{id}` | Delete snapshot |

### Widgets & Statistics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/widgets` | Generate default widget set |
| GET | `/dashboard/statistics` | Aggregate dashboard statistics |

### Timeline
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/timeline` | Empty timeline |
| POST | `/dashboard/timeline` | Build timeline from events |

### Subsystem Summaries
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/system` | System overview |
| GET | `/dashboard/trading` | Trading overview |
| GET | `/dashboard/scanner` | Scanner summary |
| GET | `/dashboard/optimization` | Optimization summary |
| GET | `/dashboard/monitoring` | Monitoring summary |
| GET | `/dashboard/portfolio` | Portfolio summary |

### User Preferences
| Method | Path | Description |
|--------|------|-------------|
| POST | `/dashboard/preferences` | Set preference |
| GET | `/dashboard/preferences/{user_id}` | List user preferences |
| GET | `/dashboard/preferences/{user_id}/{key}` | Get specific preference |
| DELETE | `/dashboard/preferences/{user_id}/{key}` | Delete preference |

### Layouts
| Method | Path | Description |
|--------|------|-------------|
| POST | `/dashboard/layouts` | Save layout |
| GET | `/dashboard/layouts/{user_id}` | List layouts |
| GET | `/dashboard/layouts/{user_id}/{name}` | Get layout |
| POST | `/dashboard/layouts/{user_id}/{name}/activate` | Set active layout |
| DELETE | `/dashboard/layouts/{user_id}/{name}` | Delete layout |

## Database Tables

| Table | Purpose |
|-------|---------|
| `dashboard_snapshots` | Persisted platform state captures |
| `dashboard_preferences` | Per-user settings (key-value) |
| `dashboard_layouts` | Per-user widget arrangements |

## Data Aggregation

The dashboard consumes data from seven subsystems — none of its own. Each `DashboardController` method accepts structured data as parameters (lists of dicts, float values) and returns an aggregated view. The controller has zero DB access, zero async, and zero side effects — it's pure transformation logic.

**Data sources consumed:**

| Dashboard View | Consumed From |
|----------------|---------------|
| System Overview | Monitoring (health checks, alerts), Infrastructure (uptime, version) |
| Trading Overview | Paper Trading / Live Trading (positions, orders), Portfolio (equity, buying power, risk utilization) |
| Scanner | Scanner (opportunities, watchlists, scans) |
| Optimization | Optimization (runs, walk-forward, Monte Carlo, rankings) |
| Monitoring | Monitoring (health, alerts, metrics, latency) |
| Portfolio | Portfolio (portfolios, accounts, allocation, exposure) |
| Timeline | All subsystems via POST (aggregation across domains) |

## Widget System

Widgets are typed, self-describing data containers rendered by the frontend. The controller generates 7 default widgets from any snapshot:
- **system-overview** — health status, broker connectivity, alert count, uptime
- **trading-overview** — open positions, P&L, risk/exposure gauges
- **portfolio-summary** — account counts, equity, allocation methods
- **monitoring-status** — health check results, active alerts, latency
- **scanner-opportunities** — top-ranked opportunities, confidence scores
- **optimization-status** — recent runs, best parameters
- **activity-timeline** — chronological event feed

Each widget carries a `refresh_interval_s` (default 30) for polling. Users can persist custom layouts via the Layouts API and set one as active.

## Timeline

The unified activity timeline merges heterogeneous events from all subsystems into a single chronological feed. Events carry:
- `event_type` — trade, alert, portfolio, optimization, scanner, broker, auth, system
- `severity` — info, warning, critical
- `source` — origin subsystem
- `metadata` — arbitrary key-value context

The controller sorts events by timestamp (newest first) and caps at the requested limit. It does not persist events — feed it from your event sources.

## Permission Model

The dashboard is read-only. All dashboard endpoints can be called without authentication — they aggregate and display data, never modify it. Exceptions:
- **Preferences API** — per-user settings scoped by `user_id`
- **Layouts API** — per-user widget arrangements scoped by `user_id`

These require a valid `user_id` parameter. In production, integrate with the Security module to enforce role-based access (operators see all dashboards, traders see trading/scanner, admins see everything).

## Known Limitations

1. **No real-time push** — all data is pull-based. Frontend must poll at configured intervals.
2. **No event persistence** — the timeline endpoint builds from provided events; it doesn't store them. Event sources must supply data on each call.
3. **In-memory aggregation only** — no caching layer. Each snapshot call recomputes all views.
4. **No downsampling for large timelines** — providing 10,000+ events may impact response time. Feed pre-filtered events.
5. **Widget layout is flat** — no drag-and-drop positioning stored; layouts store widget visibility/order only.
6. **No alert threshold configuration** — severity levels are informational, not configurable per-user.

## Design Decisions

1. **Pure functions**: `DashboardController` methods take data as parameters — no DB access, no async, no side effects. The service layer handles persistence separately.
2. **Snapshot as single source**: One `snapshot()` call captures all subsystem views at one moment. Widgets and statistics derive from snapshots.
3. **Timeline is consumption-only**: The controller builds timelines from provided events — it doesn't collect or store them. Feed it events from alerting, trading, scanning, etc.
4. **No duplication**: Every aggregation method produces net-new views. No existing engine logic is repeated.
5. **7 default widgets**: system, trading, portfolio, monitoring, scanner, optimization, timeline — generated automatically from any snapshot.
