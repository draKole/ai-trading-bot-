"""Market Data Validator — detects duplicates, gaps, and corruption."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import structlog

from app.services.market_data.provider import OHLCVBar, TIMEFRAME_MINUTES

logger = structlog.get_logger()


class ValidationResult:
    """Result of a data validation pass."""

    def __init__(self):
        self.duplicates: list[OHLCVBar] = []
        self.invalid_bars: list[tuple[OHLCVBar, list[str]]] = []
        self.gaps: list[dict] = []
        self.valid_bars: list[OHLCVBar] = []

    @property
    def total_rejected(self) -> int:
        return len(self.duplicates) + len(self.invalid_bars)

    @property
    def is_clean(self) -> bool:
        return self.total_rejected == 0 and len(self.gaps) == 0


class BarValidator:
    """Validate and deduplicate OHLCV bar data."""

    @staticmethod
    def validate_and_deduplicate(bars: list[OHLCVBar]) -> ValidationResult:
        """Run all validation checks on a list of bars.

        Gaps are evaluated independently for every instrument/timeframe/provider
        series. A mixed import therefore cannot report a false gap when two
        otherwise valid series have timestamps interleaved in the same upload.
        """
        result = ValidationResult()
        if not bars:
            return result

        valid: list[OHLCVBar] = []
        for bar in bars:
            errors = bar.validate()
            if errors:
                result.invalid_bars.append((bar, errors))
            else:
                valid.append(bar)

        seen: set[tuple[str, str, datetime, str]] = set()
        deduped: list[OHLCVBar] = []
        for bar in sorted(valid, key=lambda b: (b.instrument, b.timeframe, b.provider, b.timestamp)):
            key = (bar.instrument, bar.timeframe, bar.timestamp, bar.provider)
            if key in seen:
                result.duplicates.append(bar)
            else:
                seen.add(key)
                deduped.append(bar)
        result.valid_bars = deduped

        series: dict[tuple[str, str, str], list[OHLCVBar]] = defaultdict(list)
        for bar in deduped:
            series[(bar.instrument, bar.timeframe, bar.provider)].append(bar)

        for (_, timeframe, _), series_bars in series.items():
            expected_minutes = TIMEFRAME_MINUTES.get(timeframe)
            if not expected_minutes or len(series_bars) < 2:
                continue
            expected_interval = timedelta(minutes=expected_minutes)
            for previous, current in zip(series_bars, series_bars[1:]):
                gap = current.timestamp - previous.timestamp
                if gap > expected_interval * 1.5:
                    result.gaps.append({
                        "instrument": current.instrument,
                        "timeframe": current.timeframe,
                        "provider": current.provider,
                        "from": previous.timestamp.isoformat(),
                        "to": current.timestamp.isoformat(),
                        "missing_bars": int(gap / expected_interval) - 1,
                    })

        if result.total_rejected > 0:
            logger.warning(
                "data_validation",
                total=len(bars),
                rejected=result.total_rejected,
                invalid=len(result.invalid_bars),
                duplicates=len(result.duplicates),
                gaps=len(result.gaps),
            )
        return result


def detect_overlapping_bars(
    existing: list[OHLCVBar],
    new_bars: list[OHLCVBar],
) -> list[OHLCVBar]:
    """Filter out new bars that already exist in the stored data."""
    existing_keys = {
        (b.instrument, b.timeframe, b.timestamp, b.provider)
        for b in existing
    }
    return [
        b for b in new_bars
        if (b.instrument, b.timeframe, b.timestamp, b.provider) not in existing_keys
    ]
