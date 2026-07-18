"""Market Structure Engine configuration.

All parameters are configurable — no hard-coded magic numbers.
Config is serialized into each event so detection is fully auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class MarketStructureConfig:
    """Configuration for market structure detection.

    Attributes:
        swing_lookback: Number of bars left AND right to confirm a swing point.
            A bar is a swing high if its high is the highest among
            [i-lookback, i+lookback]. Default: 5.

        swing_confirmation_bars: How many bars must pass AFTER the potential
            swing point before it's considered "confirmed". Prevents repainting.
            Default: 1 (meaning the swing is confirmed after 1 bar closes).

        min_structure_distance_bars: Minimum number of bars between consecutive
            swing points of the same type (highs or lows). Prevents noise.
            Default: 3.

        bos_requires_close: If True, BOS requires a bar CLOSE beyond the level.
            If False, a wick through the level counts. Default: True.

        choch_requires_close: Same as above for CHoCH. Default: True.

        mss_requires_retest: If True, MSS requires a subsequent retest of
            the broken level after the break. Default: False (CHoCH + close = MSS).

        use_body_for_breaks: If True, use candle body (open/close) to determine
            breaks instead of high/low wicks. Default: False.

        min_swing_size_pct: Minimum swing size as percentage of price.
            Filters out tiny micro-swings. 0 = disabled. Default: 0.0.
    """

    swing_lookback: int = 5
    swing_confirmation_bars: int = 1
    min_structure_distance_bars: int = 3

    bos_requires_close: bool = True
    choch_requires_close: bool = True
    mss_requires_retest: bool = False

    use_body_for_breaks: bool = False
    min_swing_size_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MarketStructureConfig:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# Default config instance
DEFAULT_STRUCTURE_CONFIG = MarketStructureConfig()
