"""
Strategy engine: decides when to LP and when to withdraw.

Core logic: LP when expected fee yield > expected IL cost.

The signal is the ratio:
    edge = fee_yield_annualized / il_cost_annualized

    - edge > threshold  →  LP active (fees outweigh IL)
    - edge <= threshold →  withdraw (IL too expensive)

The threshold is the key tunable parameter. threshold=1.0 means
"LP only when fees strictly exceed IL cost." In practice you want
some margin (e.g., 1.2 = require 20% edge over IL).
"""

from dataclasses import dataclass


@dataclass
class Signal:
    """Strategy output for a single timestep."""
    timestamp: object
    lp_active: bool
    fee_yield_ann: float   # annualized fee yield
    il_cost_ann: float     # annualized IL cost estimate
    edge: float            # fee_yield / il_cost (inf if il_cost=0)
    vol: float             # current vol estimate
    price: float
    shock: bool = False    # whether shock detector triggered


def evaluate(
    fee_yield_ann: float,
    il_cost_ann: float,
    threshold: float = 1.0,
) -> bool:
    """Should the position be active?

    Args:
        fee_yield_ann: Annualized fee yield (fraction, e.g., 0.25 = 25%).
        il_cost_ann: Annualized IL cost as fraction of position value.
        threshold: Required edge ratio. 1.0 = break even, >1.0 = margin of safety.

    Returns:
        True if LP should be active.
    """
    if il_cost_ann <= 0:
        # No IL cost → always LP (free money)
        return True

    if fee_yield_ann <= 0:
        # No fees → never LP
        return False

    edge = fee_yield_ann / il_cost_ann
    return edge > threshold
