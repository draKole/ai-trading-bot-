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

## Design Decisions

1. **Pure functions**: `DashboardController` methods take data as parameters — no DB access, no async, no side effects. The service layer handles persistence separately.
2. **Snapshot as single source**: One `snapshot()` call captures all subsystem views at one moment. Widgets and statistics derive from snapshots.
3. **Timeline is consumption-only**: The controller builds timelines from provided events — it doesn't collect or store them. Feed it events from alerting, trading, scanning, etc.
4. **No duplication**: Every aggregation method produces net-new views. No existing engine logic is repeated.
5. **7 default widgets**: system, trading, portfolio, monitoring, scanner, optimization, timeline — generated automatically from any snapshot.
