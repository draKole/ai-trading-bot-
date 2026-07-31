# DevOps Bootstrap Contract — Application Settings

## Overview
The `application_settings` table stores safe, non-sensitive trading defaults
that the browser-based Settings workspace can display and update. Secrets
(database URLs, broker keys, Redis URLs, secret keys) are NEVER stored here —
those remain in environment variables only.

## Migration
- **Version:** 028_application_settings
- **Down revision:** 027_trading_audit_logs
- **File:** `backend/database/migrations/versions/028_application_settings.py`
- **Table:** `application_settings`
- **Singleton row:** id=1, seeded automatically on upgrade

## Table Schema
| Column                  | Type           | Default      |
|-------------------------|----------------|--------------|
| id                      | INTEGER (PK)   | 1            |
| trading_mode            | VARCHAR(20)    | 'PAPER'      |
| data_provider           | VARCHAR(30)    | 'yfinance'   |
| default_risk_percent    | FLOAT          | 1.0          |
| min_risk_reward         | FLOAT          | 2.0          |
| max_contracts           | INTEGER        | 10           |
| max_trades_per_day      | INTEGER        | 10           |
| max_trades_per_session  | INTEGER        | 5            |
| updated_at              | TIMESTAMPTZ    | now()        |
| created_at              | TIMESTAMPTZ    | now()        |

## Environment Variables (NOT stored in this table)
These remain in the deployment environment and are NEVER exposed through
the settings API:

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `BROKER_API_KEY` / `BROKER_SECRET`
- `DATA_PROVIDER_API_KEY`
- Any other credential or secret

## API Endpoints
- `GET /api/v1/settings/` — returns current settings (from DB with env fallback)
- `PUT /api/v1/settings/` — partial update (validated, unknown keys silently dropped)

## Bootstrap Order
1. Run all migrations up to 028: `alembic upgrade head`
2. The singleton row (id=1) is seeded automatically
3. No manual seed data needed
4. Verify: `GET /api/v1/settings/` returns 200 with all seven fields

## Validation
- `trading_mode`: "PAPER" or "LIVE" only
- `default_risk_percent`: 0.0–100.0
- `min_risk_reward`: > 0
- `max_contracts`, `max_trades_per_day`, `max_trades_per_session`: >= 1
