# Risk Engine Specification

The risk engine is the **final gatekeeper** — it has veto power over every trade regardless of signal quality.

## Check Pipeline (ordered)

1. Kill switch active?
2. Stale signal?
3. Duplicate signal?
4. Max open positions?
5. Max daily trades?
6. Max session trades?
7. Daily loss limit?
8. Max drawdown?
9. Trailing drawdown?
10. Consecutive losses?
11. Min R:R?
12. Contract limit?
13. Risk per trade?

## Kill Switch Triggers

- Manual (UI button)
- Max drawdown breached
- Trailing drawdown breached
- Broker disconnect > N seconds
- Consecutive system errors
- Position mismatch detected

## Risk Profiles

Configurable per account type:
- Default (personal account)
- Prop-firm-specific (Topstep, Apex, etc.)

Each profile specifies:
- Risk per trade %
- Max daily loss %
- Max trailing drawdown %
- Max contracts
- Max trades per day/session
- Max consecutive losses
- Min R:R
