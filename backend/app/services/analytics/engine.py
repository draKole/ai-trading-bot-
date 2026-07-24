"""Performance Analytics Engine — deterministic analysis of completed backtests.

Consumes BacktestRun, BacktestTrade, and BacktestMetrics records from
Phase 5B. Never processes historical bars directly.

All calculations are pure functions — same input data → same output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict


# ─── Helper: safe division ──────────────────────────────────

def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


# ─── Risk-Adjusted Returns ──────────────────────────────────

def compute_sharpe_ratio(returns: list[float], risk_free_rate: float = 0.02) -> float:
    """Sharpe Ratio = (mean excess return) / std dev of returns."""
    if len(returns) < 2:
        return 0.0
    mean_ret = sum(returns) / len(returns)
    excess = mean_ret - (risk_free_rate / 252)  # daily risk-free
    variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance)
    if std_dev == 0:
        return 0.0
    return round(excess / std_dev * math.sqrt(252), 4)  # annualized


def compute_sortino_ratio(returns: list[float], risk_free_rate: float = 0.02,
                          target: float = 0.0) -> float:
    """Sortino Ratio = (mean return - target) / downside deviation."""
    if len(returns) < 2:
        return 0.0
    mean_ret = sum(returns) / len(returns)
    excess = mean_ret - (risk_free_rate / 252)
    downside = [(min(r - target, 0)) ** 2 for r in returns]
    downside_sum = sum(downside)
    if downside_sum == 0:
        return 0.0
    downside_dev = math.sqrt(downside_sum / (len(returns) - 1))
    if downside_dev == 0:
        return 0.0
    return round(excess / downside_dev * math.sqrt(252), 4)


def compute_calmar_ratio(cagr: float, max_drawdown_pct: float) -> float:
    """Calmar Ratio = CAGR / |max drawdown %|."""
    if max_drawdown_pct == 0:
        return 0.0
    return round(cagr / abs(max_drawdown_pct), 4)


# ─── Drawdown Analytics ────────────────────────────────────

def compute_drawdown_analytics(equity_points: list[dict]) -> dict:
    """Compute drawdown statistics from equity curve points."""
    if not equity_points:
        return {
            "average_drawdown": 0.0, "max_dd_duration": 0,
            "recovery_time": 0, "recovery_factor": 0.0,
            "ulcer_index": 0.0,
        }

    drawdowns = [ep.get("drawdown", 0) for ep in equity_points]
    active_drawdowns = [d for d in drawdowns if d > 0]
    avg_dd = sum(active_drawdowns) / len(active_drawdowns) if active_drawdowns else 0.0

    # Max DD duration: count consecutive points where drawdown > 0
    max_dd_dur = 0
    current_dur = 0
    for d in drawdowns:
        if d > 0:
            current_dur += 1
            max_dd_dur = max(max_dd_dur, current_dur)
        else:
            current_dur = 0

    # Recovery time: trades to return to peak after max drawdown
    recovery = 0
    peak_val = 0.0
    peak_idx = 0
    for i, ep in enumerate(equity_points):
        eq = ep.get("equity", 0)
        if eq > peak_val:
            peak_val = eq
            peak_idx = i
    recovery = len(equity_points) - peak_idx - 1 if peak_idx < len(equity_points) - 1 else 0

    # Recovery factor: net profit / max drawdown
    peak_eq = max(ep.get("peak_equity", 0) for ep in equity_points) if equity_points else 1.0
    last_eq = equity_points[-1].get("equity", peak_eq) if equity_points else peak_eq
    max_dd = max(drawdowns) if drawdowns else 0.0
    recovery_factor = _safe_div(peak_eq - (peak_eq - max_dd), max(max_dd, 0.01), 0.0)
    # Simplified: net profit / max drawdown
    net_profit = last_eq - (equity_points[0].get("equity", last_eq) if equity_points else last_eq)
    recovery_factor = _safe_div(abs(net_profit), max(max_dd, 0.01), 0.0) if net_profit > 0 else 0.0

    # Ulcer Index: sqrt(mean of squared drawdown percentages)
    dd_pcts = [ep.get("drawdown_pct", 0) for ep in equity_points]
    squared = [d ** 2 for d in dd_pcts]
    ulcer_index = math.sqrt(sum(squared) / len(squared)) if squared else 0.0

    return {
        "average_drawdown": round(avg_dd, 2),
        "max_dd_duration": max_dd_dur,
        "recovery_time": recovery,
        "recovery_factor": round(recovery_factor, 4),
        "ulcer_index": round(ulcer_index, 2),
    }


# ─── Return Analytics ──────────────────────────────────────

def compute_returns_analytics(trades: list[dict],
                              equity_points: list[dict] | None = None) -> dict:
    """Compute return statistics from trade data."""
    if not trades:
        return {
            "cagr": 0.0, "avg_monthly_return": 0.0,
            "best_month": 0.0, "worst_month": 0.0,
            "monthly_returns": {},
            "best_month_label": "", "worst_month_label": "",
        }

    pnls = [t.get("pnl", 0) for t in trades]
    initial_balance = 100_000.0

    # CAGR
    if equity_points and len(equity_points) > 1:
        first_ts = equity_points[0].get("timestamp")
        last_ts = equity_points[-1].get("timestamp")
        initial = equity_points[0].get("equity", initial_balance)
        final = equity_points[-1].get("equity", initial_balance)
        if first_ts and last_ts and initial > 0:
            try:
                t1 = datetime.fromisoformat(str(first_ts).replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
                years = max((t2 - t1).total_seconds() / (365.25 * 86400), 0.01)
                cagr = ((final / initial) ** (1 / years)) - 1
            except Exception:
                cagr = 0.0
        else:
            cagr = 0.0
    else:
        cagr = 0.0

    # Monthly returns
    monthly: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        entry = t.get("entry_time", "")
        if entry:
            try:
                dt = datetime.fromisoformat(str(entry).replace("Z", "+00:00"))
                key = f"{dt.year}-{dt.month:02d}"
                monthly[key].append(t.get("pnl", 0))
            except Exception:
                pass

    monthly_totals = {k: round(sum(v), 2) for k, v in monthly.items()}
    monthly_values = list(monthly_totals.values())

    avg_monthly = sum(monthly_values) / len(monthly_values) if monthly_values else 0.0
    best_month = max(monthly_values) if monthly_values else 0.0
    worst_month = min(monthly_values) if monthly_values else 0.0

    best_label = max(monthly_totals, key=monthly_totals.get) if monthly_totals else ""
    worst_label = min(monthly_totals, key=monthly_totals.get) if monthly_totals else ""

    return {
        "cagr": round(cagr, 6),
        "avg_monthly_return": round(avg_monthly, 2),
        "best_month": round(best_month, 2),
        "worst_month": round(worst_month, 2),
        "monthly_returns": monthly_totals,
        "best_month_label": best_label,
        "worst_month_label": worst_label,
    }


# ─── Trade Analytics ───────────────────────────────────────

def compute_trade_analytics(trades: list[dict]) -> dict:
    """Compute advanced trade statistics."""
    if not trades:
        return {
            "avg_hold_time_seconds": 0.0, "median_hold_time_seconds": 0.0,
            "avg_winning_hold_time": 0.0, "avg_losing_hold_time": 0.0,
            "avg_time_between_trades": 0.0,
            "pnl_distribution": [], "r_distribution": [],
            "win_loss_histogram": {},
            "consecutive_distribution": {},
        }

    durations = [t.get("duration_seconds", 0) for t in trades]
    avg_dur = sum(durations) / len(durations)
    sorted_dur = sorted(durations)
    median_dur = sorted_dur[len(sorted_dur) // 2]

    win_durs = [t.get("duration_seconds", 0) for t in trades if t.get("pnl", 0) > 0]
    loss_durs = [t.get("duration_seconds", 0) for t in trades if t.get("pnl", 0) < 0]
    avg_win_dur = sum(win_durs) / len(win_durs) if win_durs else 0.0
    avg_loss_dur = sum(loss_durs) / len(loss_durs) if loss_durs else 0.0

    # Time between trades
    gaps: list[float] = []
    for i in range(1, len(trades)):
        e1 = trades[i - 1].get("exit_time", "")
        e2 = trades[i].get("entry_time", "")
        if e1 and e2:
            try:
                t1 = datetime.fromisoformat(str(e1).replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(str(e2).replace("Z", "+00:00"))
                gaps.append((t2 - t1).total_seconds())
            except Exception:
                pass
    avg_gap = sum(gaps) / len(gaps) if gaps else 0.0

    # P&L distribution (buckets)
    pnls = [t.get("pnl", 0) for t in trades]
    pnl_dist = _bucket_values(pnls, 10)

    # R distribution
    rs = [t.get("r_multiple", 0) for t in trades]
    r_dist = _bucket_values(rs, 10)

    # Win/loss histogram
    win_loss_hist = {"wins": 0, "losses": 0, "breakeven": 0}
    for t in trades:
        p = t.get("pnl", 0)
        if p > 0:
            win_loss_hist["wins"] += 1
        elif p < 0:
            win_loss_hist["losses"] += 1
        else:
            win_loss_hist["breakeven"] += 1

    # Consecutive distribution
    streaks: list[int] = []
    current = 0
    current_type = None
    for t in trades:
        p = t.get("pnl", 0)
        ttype = "win" if p > 0 else ("loss" if p < 0 else "even")
        if current_type is None:
            current_type = ttype
            current = 1
        elif ttype == current_type:
            current += 1
        else:
            streaks.append(current)
            current_type = ttype
            current = 1
    if current > 0:
        streaks.append(current)

    from collections import Counter
    consec_dist = dict(Counter(streaks))

    return {
        "avg_hold_time_seconds": round(avg_dur, 1),
        "median_hold_time_seconds": round(median_dur, 1),
        "avg_winning_hold_time": round(avg_win_dur, 1),
        "avg_losing_hold_time": round(avg_loss_dur, 1),
        "avg_time_between_trades": round(avg_gap, 1),
        "pnl_distribution": pnl_dist,
        "r_distribution": r_dist,
        "win_loss_histogram": win_loss_hist,
        "consecutive_distribution": consec_dist,
    }


def _bucket_values(values: list[float], num_buckets: int = 10) -> list[dict]:
    """Bucket values into evenly-spaced ranges."""
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if lo == hi:
        return [{"range": f"{lo:.2f}-{hi:.2f}", "count": len(values)}]
    step = (hi - lo) / num_buckets
    buckets = [{"range": f"{lo + i*step:.2f}-{lo + (i+1)*step:.2f}", "count": 0}
               for i in range(num_buckets)]
    for v in values:
        idx = min(int((v - lo) / step), num_buckets - 1) if step > 0 else 0
        buckets[idx]["count"] += 1
    return buckets


# ─── Rolling Analytics ─────────────────────────────────────

def compute_rolling_analytics(trades: list[dict],
                              window: int = 10) -> dict:
    """Compute rolling statistics: equity, drawdown, win rate, expectancy."""
    if not trades or len(trades) < window:
        return {
            "rolling_equity": [], "rolling_drawdown": [],
            "rolling_win_rate": [], "rolling_expectancy": [],
        }

    balance = 100_000.0
    peak = balance
    rolling_equity: list[dict] = []
    rolling_drawdown: list[dict] = []
    rolling_win_rate: list[dict] = []
    rolling_expectancy: list[dict] = []

    for i, t in enumerate(trades):
        balance += t.get("pnl", 0)
        peak = max(peak, balance)
        dd = peak - balance
        dd_pct = (dd / peak * 100) if peak > 0 else 0.0

        rolling_equity.append({"trade_index": i, "equity": round(balance, 2)})
        rolling_drawdown.append({"trade_index": i, "drawdown_pct": round(dd_pct, 2)})

        if i >= window - 1:
            window_trades = trades[i - window + 1:i + 1]
            wins = sum(1 for wt in window_trades if wt.get("pnl", 0) > 0)
            wr = wins / window
            avg_win = sum(wt.get("pnl", 0) for wt in window_trades if wt.get("pnl", 0) > 0) / max(wins, 1)
            avg_loss = sum(abs(wt.get("pnl", 0)) for wt in window_trades if wt.get("pnl", 0) < 0) / max(window - wins, 1)
            exp_val = wr * avg_win - (1 - wr) * avg_loss

            rolling_win_rate.append({"trade_index": i, "win_rate": round(wr, 4)})
            rolling_expectancy.append({"trade_index": i, "expectancy": round(exp_val, 2)})

    return {
        "rolling_equity": rolling_equity,
        "rolling_drawdown": rolling_drawdown,
        "rolling_win_rate": rolling_win_rate,
        "rolling_expectancy": rolling_expectancy,
    }


# ─── Report Generator ──────────────────────────────────────

def generate_report(run_data: dict, trades: list[dict],
                    metrics: dict, equity_points: list[dict]) -> dict:
    """Generate a complete analytics report from backtest data."""
    pnl_values = [t.get("pnl", 0) for t in trades]
    returns = [_safe_div(p, 100_000.0, 0.0) for p in pnl_values] if pnl_values else []

    # Risk-adjusted
    sharpe = compute_sharpe_ratio(returns)
    sortino = compute_sortino_ratio(returns)
    calmar = compute_calmar_ratio(
        metrics.get("cagr", 0) if "cagr" in metrics else 0.0,
        metrics.get("max_drawdown_pct", 0),
    )

    # Drawdown analytics
    dd_analytics = compute_drawdown_analytics(equity_points)

    # Returns analytics
    returns_analytics = compute_returns_analytics(trades, equity_points)

    # Trade analytics
    trade_analytics = compute_trade_analytics(trades)

    # Rolling analytics
    rolling = compute_rolling_analytics(trades)

    # Executive summary
    summary = {
        "instrument": run_data.get("instrument", ""),
        "timeframe": run_data.get("timeframe", ""),
        "total_trades": metrics.get("total_trades", 0),
        "net_profit": metrics.get("net_profit", 0),
        "win_rate": metrics.get("win_rate", 0),
        "profit_factor": metrics.get("profit_factor", 0),
        "expectancy": metrics.get("expectancy", 0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "cagr": returns_analytics.get("cagr", 0),
    }

    # Chart datasets
    charts = {
        "equity_curve": [
            {"x": ep.get("trade_index", i), "y": ep.get("equity", 0)}
            for i, ep in enumerate(equity_points)
        ],
        "drawdown_curve": [
            {"x": ep.get("trade_index", i), "y": ep.get("drawdown_pct", 0)}
            for i, ep in enumerate(equity_points)
        ],
        "monthly_returns": [
            {"x": k, "y": v}
            for k, v in returns_analytics.get("monthly_returns", {}).items()
        ],
        "trade_distribution": trade_analytics.get("pnl_distribution", []),
        "rolling_win_rate": rolling.get("rolling_win_rate", []),
        "rolling_expectancy": rolling.get("rolling_expectancy", []),
    }

    report = {
        "run_id": run_data.get("id", 0),
        "report_type": "full",
        "executive_summary": summary,
        "risk_summary": {
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            **dd_analytics,
        },
        "performance_summary": {
            **returns_analytics,
            "cagr": returns_analytics.get("cagr", 0),
        },
        "trade_statistics": trade_analytics,
        "drawdown_analysis": dd_analytics,
        "monthly_performance": returns_analytics.get("monthly_returns", {}),
        "charts": charts,
    }

    return report


# ─── Strategy Comparison ───────────────────────────────────

def compare_strategies(runs_data: list[dict]) -> dict:
    """Compare multiple backtest runs side by side."""
    if not runs_data:
        return {"runs": [], "comparison": {}}

    comparison = {
        "run_count": len(runs_data),
        "by_metric": {},
        "best_run": None,
        "worst_run": None,
    }

    profits = []
    for rd in runs_data:
        metrics = rd.get("metrics", {})
        profits.append({
            "run_id": rd.get("run_id", 0),
            "net_profit": metrics.get("net_profit", 0),
            "win_rate": metrics.get("win_rate", 0),
            "profit_factor": metrics.get("profit_factor", 0),
            "expectancy": metrics.get("expectancy", 0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
            "total_trades": metrics.get("total_trades", 0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0),
        })

    if profits:
        best = max(profits, key=lambda x: x["net_profit"])
        worst = min(profits, key=lambda x: x["net_profit"])
        comparison["best_run"] = best
        comparison["worst_run"] = worst

    comparison["runs"] = profits
    comparison["by_metric"] = {
        "avg_net_profit": round(sum(p["net_profit"] for p in profits) / len(profits), 2),
        "avg_win_rate": round(sum(p["win_rate"] for p in profits) / len(profits), 4),
        "avg_profit_factor": round(sum(p["profit_factor"] for p in profits) / len(profits), 4),
        "avg_expectancy": round(sum(p["expectancy"] for p in profits) / len(profits), 2),
        "avg_max_dd": round(sum(p["max_drawdown_pct"] for p in profits) / len(profits), 2),
        "total_trades_all": sum(p["total_trades"] for p in profits),
    }

    return {"runs": profits, "comparison": comparison}


# ─── Analytics Controller ──────────────────────────────────

class AnalyticsController:
    """Orchestrates analytics generation from backtest data.

    Consumes Phase 5B data only — never processes historical bars.
    """

    def __init__(self):
        pass

    def analyze(self, run_data: dict, trades: list[dict],
                metrics: dict, equity_points: list[dict]) -> dict:
        """Generate a full analytics report for one run."""
        return generate_report(run_data, trades, metrics, equity_points)

    def compare(self, runs: list[dict]) -> dict:
        """Compare multiple runs."""
        return compare_strategies(runs)

    def summarize(self, run_data: dict, metrics: dict) -> dict:
        """Generate executive summary only."""
        returns = [_safe_div(t.get("pnl", 0), 100_000.0, 0.0)
                   for t in run_data.get("trades", [])]
        sharpe = compute_sharpe_ratio(returns) if returns else 0.0

        return {
            "instrument": run_data.get("instrument", ""),
            "total_trades": metrics.get("total_trades", 0),
            "net_profit": metrics.get("net_profit", 0),
            "win_rate": metrics.get("win_rate", 0),
            "profit_factor": metrics.get("profit_factor", 0),
            "expectancy": metrics.get("expectancy", 0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
            "sharpe_ratio": sharpe,
        }
