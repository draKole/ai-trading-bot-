# Strategy Specification

## Core Concepts

### Market Structure
- Swing highs/lows (N-bar lookback)
- Higher highs/lows, Lower highs/lows
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Market Structure Shift (MSS)

### Liquidity
- Session highs/lows (Asian, London, NY)
- Previous Day/Week High/Low
- Equal highs/lows, Swing liquidity
- Sweep classification: approached, touched, swept, rejected, closed-through

### Fair Value Gaps
- Bullish/Bearish FVG detection
- Fill tracking (percentage, mitigation)
- Multi-timeframe overlap scoring

### Order Blocks
- Configurable detection parameters
- Mitigation and invalidation tracking

### SMT Divergence
- Correlated pair comparison (NQ/ES, MNQ/MES)
- Modular — can be enabled/disabled

### Confluence Scoring
Configurable weights:
- HTF alignment: +2
- Liquidity sweep: +2
- MSS confirmation: +2
- FVG confirmation: +1
- MTF FVG overlap: +2
- SMT divergence: +1
- Order block confluence: +1
- Session timing: +0.5
- Premium/discount: +1
- R:R potential: +1

Minimum threshold: 5.0 (configurable)

## Setup Logic
Example LONG setup:
1. HTF bullish bias
2. Price reaches/sweeps sell-side liquidity
3. Bullish MSS/CHoCH
4. Bullish displacement
5. Bullish FVG created
6. Price retraces into FVG
7. Entry with defined invalidation
8. Target: opposing liquidity

Every component individually configurable for backtesting optimization.
