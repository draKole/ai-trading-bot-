"""Bar Aggregator — builds higher-timeframe bars from lower-timeframe bars.

Uses Polars for efficient time-series aggregation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

from app.services.market_data.provider import (
    OHLCVBar,
    VALID_TIMEFRAMES,
    TIMEFRAME_MINUTES,
    TIMEFRAME_REQUIRES,
)


class BarAggregator:
    """Aggregate lower-timeframe bars into higher-timeframe bars.

    Example: 1m bars → 5m, 15m, 1h, 4h, 1d.

    Uses Polars groupby_dynamic for efficient time-bucket aggregation.
    """

    @staticmethod
    def aggregate(
        bars: list[OHLCVBar],
        target_timeframe: str,
    ) -> list[OHLCVBar]:
        """Aggregate a list of bars to a higher timeframe.

        Args:
            bars: Source bars (lower timeframe).
            target_timeframe: Target higher timeframe (must be valid).

        Returns:
            Aggregated bars at the target timeframe.
        """
        if not bars:
            return []

        if target_timeframe not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe: {target_timeframe}. "
                f"Valid: {VALID_TIMEFRAMES}"
            )

        source_tf = bars[0].timeframe
        source_minutes = TIMEFRAME_MINUTES.get(source_tf, 1)
        target_minutes = TIMEFRAME_MINUTES[target_timeframe]

        if target_minutes <= source_minutes:
            raise ValueError(
                f"Cannot aggregate {source_tf} → {target_timeframe}: "
                f"target ({target_minutes}m) must be greater than source ({source_minutes}m)"
            )

        if target_minutes % source_minutes != 0:
            raise ValueError(
                f"Cannot aggregate {source_tf} → {target_timeframe}: "
                f"target ({target_minutes}m) is not a multiple of source ({source_minutes}m)"
            )

        # Build Polars DataFrame
        rows = [
            {
                "timestamp": b.timestamp,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                # A provider may omit VWAP.  Its typical price is the same
                # approximation used by the provider normalization layer.
                "vwap_numerator": (b.vwap or b.typical_price) * b.volume,
                "session": b.session,
            }
            for b in bars
        ]
        df = pl.DataFrame(rows).sort("timestamp")

        # Time bucket in minutes
        bucket_ms = f"{target_minutes}m"

        aggregated = (
            df.group_by_dynamic(
                "timestamp",
                every=bucket_ms,
                period=bucket_ms,
                closed="left",
                label="left",
            )
            .agg([
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
                pl.col("vwap_numerator").sum().alias("vwap_numerator"),
                pl.col("session").first().alias("session"),
            ])
            .with_columns(
                pl.when(pl.col("volume") > 0)
                .then(pl.col("vwap_numerator") / pl.col("volume"))
                .otherwise((pl.col("high") + pl.col("low") + pl.col("close")) / 3.0)
                .alias("vwap")
            )
            .sort("timestamp")
        )

        result: list[OHLCVBar] = []
        for row in aggregated.iter_rows(named=True):
            result.append(OHLCVBar(
                instrument=bars[0].instrument,
                timeframe=target_timeframe,
                timestamp=row["timestamp"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                provider=bars[0].provider,
                vwap=round(float(row["vwap"]), 6),
                session=row["session"] or "",
            ))

        return result

    @staticmethod
    def build_all_timeframes(
        base_bars: list[OHLCVBar],
    ) -> dict[str, list[OHLCVBar]]:
        """Build all higher timeframes from 1-minute base bars.

        Returns a dict mapping timeframe → list of OHLCVBar.
        """
        if not base_bars:
            return {}

        result: dict[str, list[OHLCVBar]] = {
            base_bars[0].timeframe: base_bars,
        }

        # Build each higher timeframe from the next one down
        build_order = ["3m", "5m", "15m", "1h", "4h", "1d"]
        for tf in build_order:
            source_tf = TIMEFRAME_REQUIRES.get(tf, base_bars[0].timeframe)
            source_bars = result.get(source_tf, base_bars)
            if source_bars:
                result[tf] = BarAggregator.aggregate(source_bars, tf)

        return result
