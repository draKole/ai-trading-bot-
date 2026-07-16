"""CSV Data Provider — imports OHLCV data from CSV files."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from app.services.market_data.provider import DataProvider, OHLCVBar


class CSVProvider(DataProvider):
    """Import OHLCV bars from CSV files.

    Expected CSV columns (header row required):
        timestamp, open, high, low, close, volume

    Optional columns:
        instrument, timeframe (if not provided, use constructor defaults)
    """

    name = "csv"

    def __init__(
        self,
        default_instrument: str = "",
        default_timeframe: str = "1d",
    ):
        self.default_instrument = default_instrument
        self.default_timeframe = default_timeframe

    async def fetch_bars(
        self,
        instrument: str = "",
        timeframe: str = "",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[OHLCVBar]:
        """CSV provider returns empty — use fetch_from_file instead."""
        return []

    async def is_available(self) -> bool:
        return True

    def load_file(self, filepath: str | Path) -> list[OHLCVBar]:
        """Load and parse a CSV file into OHLCVBar objects."""
        bars: list[OHLCVBar] = []
        errors: list[dict] = []

        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)

            # Validate required columns
            required = {"timestamp", "open", "high", "low", "close", "volume"}
            if not required.issubset(set(reader.fieldnames or [])):
                missing = required - set(reader.fieldnames or [])
                raise ValueError(
                    f"CSV missing required columns: {missing}. "
                    f"Found: {reader.fieldnames}"
                )

            for row_num, row in enumerate(reader, start=2):
                try:
                    bar = OHLCVBar(
                        instrument=row.get("instrument", self.default_instrument),
                        timeframe=row.get("timeframe", self.default_timeframe),
                        timestamp=datetime.fromisoformat(row["timestamp"].strip()),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(float(row["volume"])),
                        provider="csv",
                    )
                    validation_errors = bar.validate()
                    if validation_errors:
                        errors.append({
                            "row": row_num,
                            "timestamp": row.get("timestamp", "?"),
                            "errors": validation_errors,
                        })
                    else:
                        bars.append(bar)
                except (ValueError, KeyError) as e:
                    errors.append({
                        "row": row_num,
                        "timestamp": row.get("timestamp", "?"),
                        "errors": [str(e)],
                    })

        if errors:
            import structlog
            logger = structlog.get_logger()
            logger.warning("csv_import_errors", count=len(errors), errors=errors[:10])

        return bars
