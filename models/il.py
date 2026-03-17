"""
Impermanent loss calculation.

Ported from BELTA _calculateIL.

IL measures how much worse LP is vs simply holding the tokens:
  IL = (lp_value / hold_value) - 1    (always <= 0)

For full-range V2-style positions:
  IL = 2*sqrt(r)/(1+r) - 1
  where r = price_new / price_old

For concentrated V3 positions, IL is amplified by the concentration factor.
The amplification comes from the leveraged exposure within the tick range.

Options-pricing connection:
  A concentrated LP position is equivalent to selling a short strangle
  (short put at p_a + short call at p_b). IL is the realized cost of
  this short gamma exposure:
    IL_cost ≈ 0.5 * gamma * sigma^2 * dt * position_value
"""

import math

from models.position import (
    hold_value_usdc,
    position_value_usdc,
    token_amounts,
)


def il_full_range(price_ratio: float) -> float:
    """Impermanent loss for a full-range (V2-style) position.

    The classic IL formula: IL = 2*sqrt(r)/(1+r) - 1

    Args:
        price_ratio: r = price_new / price_old (must be > 0).

    Returns:
        IL as a negative fraction (e.g., -0.0572 for 5.72% loss).
    """
    assert price_ratio > 0, f"Price ratio must be positive, got {price_ratio}"
    r = price_ratio
    return 2.0 * math.sqrt(r) / (1.0 + r) - 1.0


def il_concentrated(
    liquidity: float,
    entry_price: float,
    current_price: float,
    price_lower: float,
    price_upper: float,
) -> float:
    """Impermanent loss for a concentrated V3 position.

    Compares current LP value against holding the initial token amounts.

    Args:
        liquidity: Position liquidity L.
        entry_price: ETH price when position was opened.
        current_price: Current ETH price.
        price_lower: Lower price bound.
        price_upper: Upper price bound.

    Returns:
        IL as a fraction (negative = loss vs hold, 0 = no IL).
    """
    # What we hold now in the LP
    lp_value = position_value_usdc(liquidity, current_price, price_lower, price_upper)

    # What we would have had by just holding the initial tokens
    initial_usdc, initial_eth = token_amounts(
        liquidity, entry_price, price_lower, price_upper
    )
    hold_val = hold_value_usdc(initial_usdc, initial_eth, current_price)

    if hold_val == 0:
        return 0.0

    return (lp_value / hold_val) - 1.0


def il_cost_from_vol(
    sigma: float,
    dt_hours: float,
    position_value: float,
    price: float,
    price_lower: float,
    price_upper: float,
) -> float:
    """Estimate IL cost using options pricing (gamma exposure).

    The core insight: a concentrated LP position has negative gamma.
    The dollar gamma of a concentrated position with liquidity L at price p:
      Gamma_$ = |d²V/dp²| * p² = L * sqrt(p) / 2

    The expected gamma PnL (= IL cost) over dt with annualized vol sigma:
      IL_cost = 0.5 * Gamma_$ * sigma² * dt = L * sqrt(p) * sigma² * dt / 4

    Since position value V = L * [2*sqrt(p) - sqrt(p_a) - p/sqrt(p_b)],
    we can express this as:
      IL_cost = position_value * sigma² * dt * concentration_factor

    Where concentration_factor = sqrt(p) / [2*(2*sqrt(p) - sqrt(p_a) - p/sqrt(p_b))]

    For narrower ranges, V per unit L is smaller, so L per dollar is larger,
    giving a higher concentration_factor and more IL cost per dollar deposited.

    Args:
        sigma: Annualized realized volatility (e.g., 0.60 for 60%).
        dt_hours: Time period in hours.
        position_value: Current position value in USDC.
        price: Current ETH price.
        price_lower: Lower price bound.
        price_upper: Upper price bound.

    Returns:
        Estimated IL cost in USDC (positive number = cost).
    """
    if sigma <= 0 or dt_hours <= 0 or position_value <= 0:
        return 0.0

    if price <= price_lower or price >= price_upper:
        # Out of range: no IL accruing (position is single-sided)
        return 0.0

    # Convert to time fraction (hours / hours_per_year)
    dt = dt_hours / 8760.0

    sp = math.sqrt(price)
    sp_a = math.sqrt(price_lower)
    sp_b = math.sqrt(price_upper)

    # Value per unit liquidity at current price
    value_per_l = 2.0 * sp - sp_a - price / sp_b

    # Concentration factor: gamma_$ per dollar of position value
    # = sqrt(p) / (2 * value_per_l)
    # Narrower range → smaller value_per_l → higher concentration
    concentration = sp / (2.0 * value_per_l)

    # IL cost = 0.5 * gamma_$ * sigma^2 * dt, expressed via position_value
    il_cost = concentration * (sigma ** 2) * dt * position_value

    return il_cost
