"""
Fee yield calculation for Uniswap V3 positions.

Ported from BELTA _feesToUSDC.

For a concentrated LP position, fees earned depend on:
  1. Total pool fees in the period
  2. Your share of active liquidity in the tick range
  3. Whether price stayed in your range during the period

In the backtest, we use pool-level feesUSD from the subgraph and
estimate the position's share based on its liquidity vs pool liquidity.
"""


def fees_earned_usdc(
    pool_fees_usd: float,
    position_liquidity: float,
    pool_liquidity: float,
    in_range: bool,
) -> float:
    """Estimate fees earned by a position in a given period.

    Args:
        pool_fees_usd: Total pool fees in USDC for the period.
        position_liquidity: Position's liquidity L.
        pool_liquidity: Pool's total active liquidity.
        in_range: Whether the position's range includes the current tick.

    Returns:
        Estimated fees earned in USDC.
    """
    if not in_range:
        return 0.0

    if pool_liquidity <= 0 or position_liquidity <= 0:
        return 0.0

    share = position_liquidity / pool_liquidity
    return pool_fees_usd * share


def fee_yield_annualized(
    fees_usd: float,
    position_value_usd: float,
    dt_hours: float,
) -> float:
    """Convert period fees to annualized yield.

    Args:
        fees_usd: Fees earned in the period.
        position_value_usd: Position value in USDC.
        dt_hours: Period length in hours.

    Returns:
        Annualized fee yield as a fraction (e.g., 0.25 = 25% APR).
    """
    if position_value_usd <= 0 or dt_hours <= 0:
        return 0.0

    period_yield = fees_usd / position_value_usd
    hours_per_year = 8760.0
    return period_yield * (hours_per_year / dt_hours)


def is_in_range(price: float, price_lower: float, price_upper: float) -> bool:
    """Check if current price is within the position's range."""
    return price_lower <= price <= price_upper
