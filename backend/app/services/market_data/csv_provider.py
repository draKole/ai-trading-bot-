"""CSV Data Provider — validates and imports OHLCV data from CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.services.market_data.provider import DataProvider, OHLCVBar


@dataclass
class CSVParseResult:
    """Successful bars and row-level parse/validation failures from a CSV."""

    bars: list[OHLCVBar]
    errors: list[dict]


class CSVProvider(DataProvider):
    """Import OHLCV data from CSV files with a header row.

    Required columns are ``timestamp, open, high, low, close, volume``.
    ``instrument`` and ``timeframe`` may be supplied per row or inherited from
    the request defaults.
    """

    name = "csv"

    def __init__(self, default_instrument: str = "", default_timeframe: str = "1d"):
        self.default_instrument = default_instrument
        self.default_timeframe = default_timeframe

    async def fetch_bars(
        self,
        instrument: str = "",
        timeframe: str = "",
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[OHLCVBar]:
        """CSV is file-backed; use :meth:`load_file_with_report`."""
        return []

    async def is_available(self) -> bool:
        return True

    def load_file_with_report(self, filepath: str | Path) -> CSVParseResult:
        """Parse CSV rows into canonical bars and retain row-level errors."""
        bars: list[OHLCVBar] = []
        errors: list[dict] = []
        with open(filepath, newline="", encoding="utf-8-sig") as file_handle:
            reader = csv.DictReader(file_handle)
            required = {"timestamp", "open", "high", "low", "close", "volume"}
            fieldnames = set(reader.fieldnames or [])
            if not required.issubset(fieldnames):
                missing = sorted(required - fieldnames)
                raise ValueError(
                    f"CSV missing required columns: {', '.join(missing)}. "
                    f"Found: {reader.fieldnames}"
                )

            for row_number, row in enumerate(reader, start=2):
                try:
                    bar = OHLCVBar.from_dict({
                        "instrument": row.get("instrument") or self.default_instrument,
                        "timeframe": row.get("timeframe") or self.default_timeframe,
                        "timestamp": row.get("timestamp"),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "volume": row.get("volume"),
                        "vwap": row.get("vwap"),
                        "session": row.get("session"),
                        "provider": self.name,
                    }, default_provider=self.name)
                    validation_errors = bar.validate()
                    if validation_errors:
                        raise ValueError("; ".join(validation_errors))
                    bars.append(bar)
                except (TypeError, ValueError) as exc:
                    errors.append({
                        "row": row_number,
                        "timestamp": row.get("timestamp", "?"),
                        "errors": [str(exc)],
                    })
        return CSVParseResult(bars=bars, errors=errors)

    def load_file(self, filepath: str | Path) -> list[OHLCVBar]:
        """Compatibility wrapper returning only valid canonical bars."""
        return self.load_file_with_report(filepath).bars
