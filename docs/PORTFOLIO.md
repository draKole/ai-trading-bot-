# Portfolio & Multi-Account Management

## Overview

Coordinates multiple broker, funded, and paper accounts without duplicating pipeline logic. Handles capital allocation, portfolio risk aggregation, and performance tracking.

## Architecture

```
PortfolioController
├── Account Management (add/remove/enable/disable)
├── Capital Allocation (equal/fixed_pct/risk_weighted/manual)
├── Portfolio Risk (exposure, drawdown, concentration)
└── Performance (equity, ranking, statistics)
```

---

## 1. Portfolio Controller

Manages portfolios as containers of accounts:

| Method | Purpose |
|--------|---------|
| `create_portfolio(name, capital)` | Create portfolio |
| `add_account(portfolio_id, account)` | Add account |
| `allocate(portfolio_id, method)` | Allocate capital |
| `get_statistics(portfolio_id)` | Portfolio stats |
| `get_performance_ranking(portfolio_id)` | Rank accounts |

---

## 2. Capital Allocation

`allocate_capital(accounts, total, method)`:

| Method | Description |
|--------|-------------|
| `equal` | Equal split across enabled accounts |
| `fixed_pct` | Percentage-based (from account.allocation_pct) |
| `fixed_dollar` | Dollar-based (uses allocation_pct as $ amount) |
| `risk_weighted` | Proportional to account priority |
| `manual` | Uses existing allocation_pct values |

---

## 3. Portfolio Risk

`calculate_portfolio_risk()` aggregates:

- Total exposure (sum of unrealized P&L)
- Max drawdown across positions
- Capital utilization (exposure / capital)
- Account count (enabled only)

---

## 4. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/portfolio/portfolios` | List portfolios |
| `GET` | `/portfolio/portfolios/{id}` | Get portfolio |
| `POST` | `/portfolio/portfolios/create` | Create |
| `POST` | `/portfolio/portfolios/{id}/accounts/add` | Add account |
| `GET` | `/portfolio/portfolios/{id}/accounts` | List accounts |
| `POST` | `/portfolio/portfolios/{id}/allocate` | Allocate capital |
| `GET` | `/portfolio/portfolios/{id}/statistics` | Stats history |
| `GET` | `/portfolio/portfolios/{id}/performance` | Performance |
| `GET` | `/portfolio/portfolios/{id}/risk` | Risk summary |

## 5. Database Schema

| Table | Purpose |
|-------|---------|
| `portfolios` | Portfolio definitions |
| `portfolio_accounts` | Accounts with allocation config |
| `allocation_rules` | Allocation method config |
| `portfolio_positions` | Aggregated positions |
| `portfolio_statistics` | Time-series portfolio stats |
