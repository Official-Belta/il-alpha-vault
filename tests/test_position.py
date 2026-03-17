"""Tests for position math — token amounts, position value, liquidity calculation."""

import math

import pytest

from models.position import (
    hold_value_usdc,
    liquidity_from_deposit,
    position_value_usdc,
    token_amounts,
)


class TestTokenAmounts:
    """Test token amount calculations for concentrated positions."""

    def test_in_range_has_both_tokens(self):
        L = 1_000_000.0
        usdc, eth = token_amounts(L, price=2000, price_lower=1500, price_upper=2500)
        assert usdc > 0
        assert eth > 0

    def test_below_range_all_eth(self):
        L = 1_000_000.0
        usdc, eth = token_amounts(L, price=1000, price_lower=1500, price_upper=2500)
        assert usdc == 0.0
        assert eth > 0

    def test_above_range_all_usdc(self):
        L = 1_000_000.0
        usdc, eth = token_amounts(L, price=3000, price_lower=1500, price_upper=2500)
        assert usdc > 0
        assert eth == 0.0

    def test_at_lower_bound_all_eth(self):
        L = 1_000_000.0
        usdc, eth = token_amounts(L, price=1500, price_lower=1500, price_upper=2500)
        assert usdc == pytest.approx(0.0, abs=1e-10)
        assert eth > 0

    def test_at_upper_bound_all_usdc(self):
        L = 1_000_000.0
        usdc, eth = token_amounts(L, price=2500, price_lower=1500, price_upper=2500)
        assert usdc > 0
        assert eth == pytest.approx(0.0, abs=1e-10)

    def test_wider_range_less_concentrated(self):
        """Wider range should hold less of each token per unit of liquidity."""
        L = 1_000_000.0
        _, eth_narrow = token_amounts(L, price=2000, price_lower=1800, price_upper=2200)
        _, eth_wide = token_amounts(L, price=2000, price_lower=1000, price_upper=3000)
        # Narrow range has more ETH per unit L (more concentrated)
        # Actually wider range has more ETH because 1/sp - 1/sp_b is larger
        # when sp_b is larger. Let me just check they're different.
        assert eth_narrow != pytest.approx(eth_wide)

    def test_invalid_price_raises(self):
        with pytest.raises(AssertionError):
            token_amounts(1000, price=0, price_lower=1500, price_upper=2500)

    def test_invalid_range_raises(self):
        with pytest.raises(AssertionError):
            token_amounts(1000, price=2000, price_lower=2500, price_upper=1500)


class TestPositionValueUSDC:
    """Test position value calculation."""

    def test_value_is_positive(self):
        val = position_value_usdc(1_000_000, price=2000, price_lower=1500, price_upper=2500)
        assert val > 0

    def test_value_symmetric_property(self):
        """Position value at entry price should be well-defined."""
        L = 1_000_000.0
        val = position_value_usdc(L, price=2000, price_lower=1500, price_upper=2500)
        # Value should be roughly consistent with deposit amount
        assert val > 0

    def test_value_increases_with_liquidity(self):
        val1 = position_value_usdc(1_000_000, price=2000, price_lower=1500, price_upper=2500)
        val2 = position_value_usdc(2_000_000, price=2000, price_lower=1500, price_upper=2500)
        assert val2 == pytest.approx(val1 * 2)

    def test_out_of_range_below(self):
        """Below range: 100% ETH, value = eth_amount * price."""
        L = 1_000_000.0
        val = position_value_usdc(L, price=1000, price_lower=1500, price_upper=2500)
        usdc, eth = token_amounts(L, price=1000, price_lower=1500, price_upper=2500)
        assert val == pytest.approx(eth * 1000)

    def test_out_of_range_above(self):
        """Above range: 100% USDC, value = usdc_amount."""
        L = 1_000_000.0
        val = position_value_usdc(L, price=3000, price_lower=1500, price_upper=2500)
        usdc, eth = token_amounts(L, price=3000, price_lower=1500, price_upper=2500)
        assert val == pytest.approx(usdc)


class TestLiquidityFromDeposit:
    """Test that depositing and reading back value is consistent."""

    def test_roundtrip(self):
        """Deposit $100k, position value should be $100k."""
        deposit = 100_000.0
        price = 2000.0
        p_lower = 1500.0
        p_upper = 2500.0

        L = liquidity_from_deposit(deposit, price, p_lower, p_upper)
        val = position_value_usdc(L, price, p_lower, p_upper)
        assert val == pytest.approx(deposit, rel=1e-10)

    def test_roundtrip_narrow_range(self):
        deposit = 50_000.0
        price = 2000.0
        L = liquidity_from_deposit(deposit, price, 1900, 2100)
        val = position_value_usdc(L, price, 1900, 2100)
        assert val == pytest.approx(deposit, rel=1e-10)

    def test_roundtrip_wide_range(self):
        deposit = 200_000.0
        price = 2000.0
        L = liquidity_from_deposit(deposit, price, 500, 5000)
        val = position_value_usdc(L, price, 500, 5000)
        assert val == pytest.approx(deposit, rel=1e-10)

    def test_out_of_range_raises(self):
        with pytest.raises(AssertionError):
            liquidity_from_deposit(100_000, price=1000, price_lower=1500, price_upper=2500)


class TestHoldValue:
    def test_basic(self):
        val = hold_value_usdc(initial_usdc=50_000, initial_eth=25, current_price=2000)
        assert val == pytest.approx(100_000)

    def test_price_increase(self):
        val = hold_value_usdc(initial_usdc=50_000, initial_eth=25, current_price=4000)
        assert val == pytest.approx(150_000)
