"""Confluence Scoring Engine — configurable, testable scoring.

Aggregates signals from all engines into a numeric score.
Weights are configurable and must be optimized through testing.
Includes a minimum-score threshold before a setup is eligible.
"""

from dataclasses import dataclass, field


@dataclass
class ConfluenceConfig:
    """Weights for each confluence factor. All configurable."""
    htf_alignment: float = 2.0
    liquidity_sweep: float = 2.0
    mss_confirmation: float = 2.0
    choch: float = 1.5
    bos: float = 1.0
    fvg: float = 1.0
    mtf_fvg_overlap: float = 2.0
    order_block: float = 1.0
    smt_divergence: float = 1.0
    session_timing: float = 0.5
    premium_discount: float = 1.0
    rr_potential: float = 1.0
    min_threshold: float = 5.0  # Minimum score for eligibility


class ConfluenceScorer:
    """Calculate confluence score from active features.

    Not yet implemented — interface defined for Phase 3.
    """
    pass
