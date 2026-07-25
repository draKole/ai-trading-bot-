"""Multi-Market Scanner Engine — scan multiple symbols, score opportunities, rank."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class WatchlistEntry:
    name: str
    description: str = ""
    symbols: list[str] = field(default_factory=list)
    timeframes: list[str] = field(default_factory=lambda: ["5m"])

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "symbols": self.symbols, "timeframes": self.timeframes,
                "symbol_count": len(self.symbols)}


@dataclass
class ScanOpportunity:
    symbol: str
    timeframe: str
    direction: str = "neutral"
    score: float = 0.0
    confidence: str = "Low"
    expected_reward: float = 0.0
    risk: float = 0.0
    rank: int = 0

    def to_dict(self) -> dict:
        return {"symbol": self.symbol, "timeframe": self.timeframe,
                "direction": self.direction, "score": round(self.score, 2),
                "confidence": self.confidence,
                "expected_reward": round(self.expected_reward, 2),
                "risk": round(self.risk, 2), "rank": self.rank}


def score_opportunity(symbol_data: dict) -> float:
    """Normalized 0-100 score from component quality signals."""
    weights = {
        "confluence": 25, "structure": 20, "liquidity": 15,
        "fvg": 15, "trend": 10, "session": 5, "volume": 10,
    }
    score = 0.0
    for key, weight in weights.items():
        value = symbol_data.get(key, 0)
        score += float(value) * weight / 100.0
    return round(min(max(score, 0), 100), 2)


def confidence_label(score: float) -> str:
    if score >= 80:
        return "Very High"
    elif score >= 65:
        return "High"
    elif score >= 50:
        return "Medium"
    elif score >= 35:
        return "Low"
    return "Very Low"


class ScannerController:
    """Scans multiple symbols/timeframes, scores and ranks opportunities.

    Never duplicates engine logic. Never executes trades.
    """

    def __init__(self):
        self._watchlists: dict[str, WatchlistEntry] = {}
        self._scan_history: list[dict] = []

    def create_watchlist(self, name: str, symbols: list[str],
                         timeframes: list[str] | None = None,
                         description: str = "") -> WatchlistEntry:
        wl = WatchlistEntry(name=name, description=description,
                            symbols=symbols,
                            timeframes=timeframes or ["5m"])
        self._watchlists[name] = wl
        return wl

    def get_watchlist(self, name: str) -> WatchlistEntry | None:
        return self._watchlists.get(name)

    def list_watchlists(self) -> list[WatchlistEntry]:
        return list(self._watchlists.values())

    def scan(self, watchlist_name: str,
             market_data: dict[str, dict] | None = None) -> list[ScanOpportunity]:
        """Scan a watchlist. market_data = {symbol: {timeframe: data}}."""
        wl = self._watchlists.get(watchlist_name)
        if wl is None:
            return []

        opportunities: list[ScanOpportunity] = []
        data = market_data or {}

        for symbol in wl.symbols:
            for tf in wl.timeframes:
                sym_data = data.get(symbol, {}).get(tf, {})
                score = score_opportunity(sym_data)
                conf = confidence_label(score)

                opp = ScanOpportunity(
                    symbol=symbol, timeframe=tf,
                    direction=sym_data.get("direction", "neutral"),
                    score=score, confidence=conf,
                    expected_reward=sym_data.get("expected_reward", 0),
                    risk=sym_data.get("risk", 0),
                )
                opportunities.append(opp)

        # Rank by score descending
        ranked = sorted(opportunities, key=lambda o: o.score, reverse=True)
        for i, o in enumerate(ranked):
            o.rank = i + 1

        self._scan_history.append({
            "watchlist": watchlist_name,
            "symbols_scanned": len(wl.symbols),
            "opportunities_found": len([o for o in opportunities if o.score > 0]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return ranked

    def get_top_opportunities(self, watchlist_name: str, top_n: int = 10,
                              market_data: dict | None = None) -> list[ScanOpportunity]:
        results = self.scan(watchlist_name, market_data)
        return results[:top_n]

    def get_statistics(self) -> dict:
        total_scans = len(self._scan_history)
        total_opps = sum(s.get("opportunities_found", 0) for s in self._scan_history)
        return {
            "total_scans": total_scans,
            "total_opportunities": total_opps,
            "watchlists": len(self._watchlists),
        }
