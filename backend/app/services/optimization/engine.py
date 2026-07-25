"""Strategy Optimization Engine — grid search, random search, walk-forward, Monte Carlo."""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class ParamRange:
    """A parameter with range and step."""
    name: str
    min_val: float
    max_val: float
    step: float = 1.0

    def generate_values(self) -> list[float]:
        vals = []
        v = self.min_val
        while v <= self.max_val:
            vals.append(round(v, 6))
            v += self.step
        return vals


def grid_search(param_ranges: list[ParamRange]) -> list[dict]:
    """Generate all combinations from parameter ranges."""
    if not param_ranges:
        return [{}]
    values = [p.generate_values() for p in param_ranges]
    return _cartesian_product(values, param_ranges)


def _cartesian_product(values: list[list[float]],
                       ranges: list[ParamRange]) -> list[dict]:
    if not values:
        return [{}]
    head = values[0]
    name = ranges[0].name
    rest = _cartesian_product(values[1:], ranges[1:])
    result = []
    for v in head:
        for r in rest:
            entry = {name: v}
            entry.update(r)
            result.append(entry)
    return result


def random_search(param_ranges: list[ParamRange],
                  n_iterations: int = 100,
                  seed: int = 42) -> list[dict]:
    """Generate random parameter combinations."""
    rng = random.Random(seed)
    results = []
    for _ in range(n_iterations):
        combo = {}
        for p in param_ranges:
            combo[p.name] = round(
                rng.uniform(p.min_val, p.max_val), 6,
            )
        results.append(combo)
    return results


def walk_forward_splits(data_length: int, in_sample: int,
                        out_sample: int) -> list[dict]:
    """Generate walk-forward split indices."""
    splits = []
    start = 0
    while start + in_sample + out_sample <= data_length:
        splits.append({
            "train_start": start,
            "train_end": start + in_sample,
            "test_start": start + in_sample,
            "test_end": start + in_sample + out_sample,
        })
        start += out_sample
    return splits


def monte_carlo_simulation(trades: list[dict],
                           iterations: int = 1000,
                           seed: int = 42) -> dict:
    """Run Monte Carlo simulation by randomizing trade sequence."""
    if not trades:
        return {
            "mean_equity": 0.0, "equity_std": 0.0,
            "risk_of_ruin": 0.0, "confidence_95_low": 0.0,
            "confidence_95_high": 0.0, "iterations": 0,
        }

    rng = random.Random(seed)
    pnls = [t.get("pnl", 0) for t in trades]
    initial_balance = 100_000.0
    final_equities: list[float] = []
    ruins = 0

    for _ in range(iterations):
        rng.shuffle(pnls)
        equity = initial_balance
        for p in pnls:
            equity += p
            if equity <= 0:
                ruins += 1
                equity = 0
                break
        final_equities.append(equity)

    mean_eq = sum(final_equities) / len(final_equities)
    variance = sum((e - mean_eq) ** 2 for e in final_equities) / (len(final_equities) - 1) if len(final_equities) > 1 else 0
    std_eq = math.sqrt(variance)
    sorted_eq = sorted(final_equities)
    lo_idx = int(len(sorted_eq) * 0.025)
    hi_idx = int(len(sorted_eq) * 0.975)

    return {
        "mean_equity": round(mean_eq, 2),
        "equity_std": round(std_eq, 2),
        "risk_of_ruin": round(ruins / iterations, 4),
        "confidence_95_low": round(sorted_eq[lo_idx], 2) if lo_idx < len(sorted_eq) else 0,
        "confidence_95_high": round(sorted_eq[hi_idx], 2) if hi_idx < len(sorted_eq) else 0,
        "iterations": iterations,
    }


def compare_strategies(results: list[dict]) -> dict:
    """Compare and rank strategies by multiple metrics."""
    if not results:
        return {"rankings": [], "best": None}

    sorted_by_profit = sorted(results, key=lambda r: r.get("net_profit", 0), reverse=True)
    return {
        "rankings": [
            {"rank": i + 1, "params": r.get("params", {}),
             "net_profit": r.get("net_profit", 0),
             "win_rate": r.get("win_rate", 0),
             "profit_factor": r.get("profit_factor", 0),
             "expectancy": r.get("expectancy", 0)}
            for i, r in enumerate(sorted_by_profit[:10])
        ],
        "best": sorted_by_profit[0] if sorted_by_profit else None,
        "total_compared": len(results),
    }


class OptimizationController:
    """Coordinates optimization runs. Never duplicates engine logic."""

    def __init__(self):
        self._runs: dict[str, dict] = {}

    def create_run(self, name: str, method: str = "grid") -> dict:
        rid = str(uuid4())
        self._runs[rid] = {
            "id": rid, "name": name, "method": method,
            "status": "pending", "results": [],
            "best_score": 0.0, "best_params": None,
        }
        return self._runs[rid]

    def run_grid_search(self, param_ranges: list[ParamRange],
                        evaluator=None) -> dict:
        """Run grid search and rank results."""
        combos = grid_search(param_ranges)
        run = self.create_run("Grid Search", "grid")
        run["total_combinations"] = len(combos)
        run["status"] = "running"

        results = []
        for combo in combos:
            score = 0.0
            if evaluator:
                score = evaluator(combo)
            results.append({"params": combo, "score": score})

        results.sort(key=lambda r: r["score"], reverse=True)
        run["results"] = results
        run["completed_combinations"] = len(results)
        run["status"] = "completed"
        if results:
            run["best_score"] = results[0]["score"]
            run["best_params"] = results[0]["params"]
        return run

    def run_monte_carlo(self, trades: list[dict],
                        iterations: int = 1000,
                        seed: int = 42) -> dict:
        return monte_carlo_simulation(trades, iterations, seed)

    def get_run(self, run_id: str) -> dict | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[dict]:
        return list(self._runs.values())
