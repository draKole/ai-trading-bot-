# Autonomous market-data synchronization

The API lifespan starts and stops `AutonomousMarketData` using the application
SQLAlchemy session factory. The scheduler is historical market-data import only
and does not enable broker execution or LIVE mode.

## Calendar and timing

`market_holidays` is a dependency-free CME equity-index futures calendar with
observed fixed holidays, recurring federal closures, and Good Friday. Early-close
sessions are not excluded because valid bars may exist. The regular sync runs once
per New York local date at or after 16:15 (DST-aware), then performs bounded
seven-day weekly integrity and 31-day monthly verification passes.

## Gap detection and safety

`find_missing_days` uses SQLAlchemy `DISTINCT DATE(timestamp)` joined to the
instrument table and only considers ES/MES/NQ/MNQ one-minute bars. Missing dates
are backfilled through the same idempotent `MarketDataService.fetch_and_ingest`
path; no synthetic bars are generated. Provider credentials remain server-side.

The `/api/v1/market-data/autonomous/health` endpoint reports scheduler state,
missing dates, provider, last sync, and weekly/monthly audit timestamps.
