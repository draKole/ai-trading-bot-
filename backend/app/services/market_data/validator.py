"""Market Data Validator — detects duplicates, gaps, and corruption."""

from __future__ import annotations

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

        Returns a ValidationResult with valid bars separated from rejected ones.
        """
        result = ValidationResult()

        if not bars:
            return result

        # 1. Remove bars with invalid values
        valid: list[OHLCVBar] = []
        for bar in bars:
            errors = bar.validate()
            if errors:
                result.invalid_bars.append((bar, errors))
            else:
                valid.append(bar)

        # 2. Detect and remove duplicates (same instrument, timeframe, timestamp, provider)
        seen: set[tuple[str, str, datetime, str]] = set()
        deduped: list[OHLCVBar] = []
        for bar in sorted(valid, key=lambda b: b.timestamp):
            key = (bar.instrument, bar.timeframe, bar.timestamp, bar.provider)
            if key in seen:
                result.duplicates.append(bar)
            else:
                seen.add(key)
                deduped.append(bar)

        result.valid_bars = deduped

        # 3. Detect gaps (missing bars in the timeline)
        if len(deduped) >= 2:
            tf_minutes = TIMEFRAME_MINUTES.get(deduped[0].timeframe)
            if tf_minutes:
                expected_interval = timedelta(minutes=tf_minutes)
                for i in range(1, len(deduped)):
                    gap = deduped[i].timestamp - deduped[i - 1].timestamp
                    if gap > expected_interval * 1.5:  # Allow small timing variance
                        missing_bars = int(gap / expected_interval) - 1
                        result.gaps.append({
                            "instrument": deduped[i].instrument,
                            "timeframe": deduped[i].timeframe,
                            "from": deduped[i - 1].timestamp.isoformat(),
                            "to": deduped[i].timestamp.isoformat(),
                            "missing_bars": missing_bars,
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
    """Filter out new bars that already exist in the stored data.

    Used at ingestion time to avoid inserting duplicate bars into the database.
    """
    existing_keys = {
        (b.instrument, b.timeframe, b.timestamp, b.provider)
        for b in existing
    }
    return [
        b for b in new_bars
        if (b.instrument, b.timeframe, b.timestamp, b.provider) not in existing_keys
    ]
