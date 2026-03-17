"""Tests for fee calculation."""

import pytest

from models.fees import fee_yield_annualized, fees_earned_usdc, is_in_range


class TestFeesEarnedUSDC:
    def test_proportional_to_share(self):
        """Fees scale linearly with liquidity share."""
        fees = fees_earned_usdc(
            pool_fees_usd=10_000,
            position_liquidity=100,
            pool_liquidity=1000,
            in_range=True,
        )
        assert fees == pytest.approx(1_000)

    def test_out_of_range_zero(self):
        fees = fees_earned_usdc(
            pool_fees_usd=10_000,
            position_liquidity=100,
            pool_liquidity=1000,
            in_range=False,
        )
        assert fees == 0.0

    def test_zero_pool_liquidity(self):
        fees = fees_earned_usdc(
            pool_fees_usd=10_000,
            position_liquidity=100,
            pool_liquidity=0,
            in_range=True,
        )
        assert fees == 0.0

    def test_full_share(self):
        """If position is all the liquidity, gets all fees."""
        fees = fees_earned_usdc(
            pool_fees_usd=5_000,
            position_liquidity=1000,
            pool_liquidity=1000,
            in_range=True,
        )
        assert fees == pytest.approx(5_000)


class TestFeeYieldAnnualized:
    def test_basic(self):
        """$100 fees on $100k in 24h = ~365% APR."""
        apr = fee_yield_annualized(fees_usd=100, position_value_usd=100_000, dt_hours=24)
        assert apr == pytest.approx(0.365 * 100 / 100, rel=0.01)
        # 100/100000 * 8760/24 = 0.365

    def test_zero_value(self):
        assert fee_yield_annualized(fees_usd=100, position_value_usd=0, dt_hours=24) == 0.0

    def test_zero_time(self):
        assert fee_yield_annualized(fees_usd=100, position_value_usd=100_000, dt_hours=0) == 0.0


class TestIsInRange:
    def test_in_range(self):
        assert is_in_range(2000, 1500, 2500) is True

    def test_at_lower_bound(self):
        assert is_in_range(1500, 1500, 2500) is True

    def test_at_upper_bound(self):
        assert is_in_range(2500, 1500, 2500) is True

    def test_below_range(self):
        assert is_in_range(1000, 1500, 2500) is False

    def test_above_range(self):
        assert is_in_range(3000, 1500, 2500) is False
