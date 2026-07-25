# Multi-Market Scanner & Opportunity Ranking

## Overview

Scans multiple symbols and timeframes, scores opportunities using 7 weighted quality signals, ranks by confidence, and tracks scan history. Never duplicates engine logic or executes trades.

## Architecture

```
Watchlist → ScannerController.scan() → Opportunity Scoring → Ranking → Results
                ↑                              ↓
          Market Data                    confidence_label()
```

---

## 1. Watchlist Management

Create multiple watchlists with custom symbol sets and timeframes. Supports 500+ symbols.

## 2. Opportunity Scoring

Weighted 0-100 composite score from:

| Signal | Weight |
|--------|--------|
| Confluence | 25 |
| Market Structure | 20 |
| Liquidity | 15 |
| FVG Quality | 15 |
| Trend Alignment | 10 |
| Session Quality | 5 |
| Volume | 10 |

### Confidence Labels
- ≥80: Very High
- ≥65: High
- ≥50: Medium
- ≥35: Low
- <35: Very Low

## 3. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/scanner/watchlists` | List watchlists |
| `POST` | `/scanner/watchlists/create` | Create |
| `POST` | `/scanner/scan` | Run scan |
| `GET` | `/scanner/scan/top` | Top N opportunities |
| `GET` | `/scanner/scans` | Scan history |
| `GET` | `/scanner/statistics` | Stats |
