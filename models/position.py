"""
Uniswap V3 concentrated liquidity position math.

Ported from BELTA _positionValueUSDC.

A concentrated LP position in range [p_a, p_b] with liquidity L holds:
  - token0 (USDC): y = L * (sqrt(p) - sqrt(p_a))      when p >= p_a
  - token1 (ETH):  x = L * (1/sqrt(p) - 1/sqrt(p_b))  when p <= p_b

Where p = ETH price in USDC terms (token1Price).

Three regimes:
  - p < p_a:  Position is 100% ETH (price dropped below range)
  - p_a <= p <= p_b:  Position holds both tokens
  - p > p_b:  Position is 100% USDC (price rose above range)
"""

import math


def token_amounts(
    liquidity: float,
    price: float,
    price_lower: float,
    price_upper: float,
) -> tuple[float, float]:
    """Calculate token amounts for a concentrated LP position.

    Args:
        liquidity: Position liquidity (L).
        price: Current ETH price in USDC.
        price_lower: Lower bound of price range.
        price_upper: Upper bound of price range.

    Returns:
        (usdc_amount, eth_amount) held by the position.
    """
    assert price > 0, f"Price must be positive, got {price}"
    assert price_lower > 0, f"price_lower must be positive, got {price_lower}"
    assert price_upper > price_lower, (
        f"price_upper must exceed price_lower: {price_upper} <= {price_lower}"
    )

    sp = math.sqrt(price)
    sp_a = math.sqrt(price_lower)
    sp_b = math.sqrt(price_upper)

    if price <= price_lower:
        # 100% ETH
        usdc = 0.0
        eth = liquidity * (1.0 / sp_a - 1.0 / sp_b)
    elif price >= price_upper:
        # 100% USDC
        usdc = liquidity * (sp_b - sp_a)
        eth = 0.0
    else:
        # In range: both tokens
        usdc = liquidity * (sp - sp_a)
        eth = liquidity * (1.0 / sp - 1.0 / sp_b)

    return usdc, eth


def position_value_usdc(
    liquidity: float,
    price: float,
    price_lower: float,
    price_upper: float,
) -> float:
    """Calculate total position value in USDC.

    Ported from BELTA _positionValueUSDC.

    Args:
        liquidity: Position liquidity (L).
        price: Current ETH price in USDC.
        price_lower: Lower bound of price range.
        price_upper: Upper bound of price range.

    Returns:
        Position value in USDC.
    """
    usdc, eth = token_amounts(liquidity, price, price_lower, price_upper)
    return usdc + eth * price


def hold_value_usdc(
    initial_usdc: float,
    initial_eth: float,
    current_price: float,
) -> float:
    """Value of simply holding the initial token amounts (no LP).

    Args:
        initial_usdc: USDC held at entry.
        initial_eth: ETH held at entry.
        current_price: Current ETH price in USDC.

    Returns:
        Hold value in USDC.
    """
    return initial_usdc + initial_eth * current_price


def liquidity_from_deposit(
    deposit_usdc: float,
    price: float,
    price_lower: float,
    price_upper: float,
) -> float:
    """Calculate liquidity L for a given USDC-denominated deposit at current price.

    Deposits are split into the correct token ratio for the given range.

    Args:
        deposit_usdc: Total deposit value in USDC.
        price: Current ETH price at deposit time.
        price_lower: Lower price bound.
        price_upper: Upper price bound.

    Returns:
        Liquidity value L.
    """
    assert price_lower < price < price_upper, (
        f"Price {price} must be within range ({price_lower}, {price_upper}) to deposit"
    )

    sp = math.sqrt(price)
    sp_a = math.sqrt(price_lower)
    sp_b = math.sqrt(price_upper)

    # Value per unit of liquidity at current price:
    # USDC component: L * (sp - sp_a)
    # ETH component valued in USDC: L * (1/sp - 1/sp_b) * price
    value_per_l = (sp - sp_a) + (1.0 / sp - 1.0 / sp_b) * price

    return deposit_usdc / value_per_l
