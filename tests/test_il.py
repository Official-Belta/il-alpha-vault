"""Tests for IL calculation — the mathematical core of the project.

Known IL values (full-range, V2-style):
  price_ratio  |  IL
  1.0          |  0.0%
  1.25         | -0.60%
  1.50         | -2.02%
  2.00         | -5.72%
  3.00         | -13.40%
  4.00         | -20.00%
  0.50         | -5.72%  (symmetric)
  0.25         | -20.00% (symmetric)

These are the canonical values from the Uniswap IL formula:
  IL = 2*sqrt(r)/(1+r) - 1
"""

import math

import pytest

from models.il import il_concentrated, il_cost_from_vol, il_full_range
from models.position import liquidity_from_deposit


class TestILFullRange:
    """Verify the classic IL formula against known values."""

    def test_no_price_change(self):
        assert il_full_range(1.0) == pytest.approx(0.0)

    def test_25pct_increase(self):
        assert il_full_range(1.25) == pytest.approx(-0.006, abs=0.001)

    def test_50pct_increase(self):
        assert il_full_range(1.50) == pytest.approx(-0.0202, abs=0.001)

    def test_2x_increase(self):
        """50% price drop or 2x increase: IL = 5.72%."""
        assert il_full_range(2.0) == pytest.approx(-0.0572, abs=0.001)

    def test_3x_increase(self):
        assert il_full_range(3.0) == pytest.approx(-0.1340, abs=0.001)

    def test_4x_increase(self):
        """4x price change: IL = 20%."""
        assert il_full_range(4.0) == pytest.approx(-0.20, abs=0.001)

    def test_50pct_drop_symmetric(self):
        """IL is the same for 2x up and 0.5x down."""
        assert il_full_range(0.5) == pytest.approx(il_full_range(2.0), abs=1e-10)

    def test_75pct_drop_symmetric(self):
        assert il_full_range(0.25) == pytest.approx(il_full_range(4.0), abs=1e-10)

    def test_always_negative_or_zero(self):
        """IL is always <= 0 (LP always underperforms hold)."""
        for r in [0.1, 0.5, 0.9, 1.0, 1.1, 2.0, 5.0, 10.0]:
            assert il_full_range(r) <= 0.0 + 1e-15

    def test_invalid_ratio_raises(self):
        with pytest.raises(AssertionError):
            il_full_range(0.0)
        with pytest.raises(AssertionError):
            il_full_range(-1.0)


class TestILConcentrated:
    """Test IL for concentrated V3 positions."""

    def test_no_price_change_no_il(self):
        """No price movement = no IL."""
        price = 2000.0
        L = liquidity_from_deposit(100_000, price, 1500, 2500)
        il = il_concentrated(L, entry_price=price, current_price=price,
                            price_lower=1500, price_upper=2500)
        assert il == pytest.approx(0.0, abs=1e-10)

    def test_il_is_negative(self):
        """Any price movement should produce negative IL."""
        price = 2000.0
        L = liquidity_from_deposit(100_000, price, 1500, 2500)
        il = il_concentrated(L, entry_price=price, current_price=2200,
                            price_lower=1500, price_upper=2500)
        assert il < 0

    def test_concentrated_il_exceeds_full_range(self):
        """Concentrated positions have MORE IL than full-range for same price move."""
        entry = 2000.0
        current = 3000.0
        r = current / entry

        # Full-range IL
        full_il = il_full_range(r)

        # Concentrated IL (narrow range)
        L = liquidity_from_deposit(100_000, entry, 1500, 2500)
        conc_il = il_concentrated(L, entry, current, 1500, 2500)

        # Concentrated IL should be worse (more negative) than full-range
        assert conc_il < full_il

    def test_narrower_range_more_il(self):
        """Narrower range = more concentrated = more IL."""
        entry = 2000.0
        current = 2200.0

        L_wide = liquidity_from_deposit(100_000, entry, 1000, 3000)
        il_wide = il_concentrated(L_wide, entry, current, 1000, 3000)

        L_narrow = liquidity_from_deposit(100_000, entry, 1800, 2200)
        il_narrow = il_concentrated(L_narrow, entry, current, 1800, 2200)

        # Narrow range should have worse IL
        assert il_narrow < il_wide

    def test_price_exits_range_below(self):
        """When price drops below range, IL is severe."""
        entry = 2000.0
        L = liquidity_from_deposit(100_000, entry, 1500, 2500)
        il = il_concentrated(L, entry, current_price=1000,
                            price_lower=1500, price_upper=2500)
        # Should be significantly negative
        assert il < -0.10

    def test_price_exits_range_above(self):
        """When price rises above range, IL is the 'missed upside'."""
        entry = 2000.0
        L = liquidity_from_deposit(100_000, entry, 1500, 2500)
        il = il_concentrated(L, entry, current_price=4000,
                            price_lower=1500, price_upper=2500)
        assert il < -0.10


class TestILCostFromVol:
    """Test the options-pricing IL cost estimator."""

    def test_zero_vol_zero_cost(self):
        cost = il_cost_from_vol(sigma=0, dt_hours=1, position_value=100_000,
                               price=2000, price_lower=1500, price_upper=2500)
        assert cost == 0.0

    def test_positive_vol_positive_cost(self):
        cost = il_cost_from_vol(sigma=0.60, dt_hours=1, position_value=100_000,
                               price=2000, price_lower=1500, price_upper=2500)
        assert cost > 0

    def test_higher_vol_higher_cost(self):
        cost_low = il_cost_from_vol(sigma=0.30, dt_hours=1, position_value=100_000,
                                    price=2000, price_lower=1500, price_upper=2500)
        cost_high = il_cost_from_vol(sigma=0.60, dt_hours=1, position_value=100_000,
                                     price=2000, price_lower=1500, price_upper=2500)
        # Cost scales with sigma^2, so 2x vol = 4x cost
        assert cost_high == pytest.approx(cost_low * 4, rel=0.01)

    def test_longer_period_higher_cost(self):
        cost_1h = il_cost_from_vol(sigma=0.60, dt_hours=1, position_value=100_000,
                                   price=2000, price_lower=1500, price_upper=2500)
        cost_24h = il_cost_from_vol(sigma=0.60, dt_hours=24, position_value=100_000,
                                    price=2000, price_lower=1500, price_upper=2500)
        assert cost_24h == pytest.approx(cost_1h * 24, rel=0.01)

    def test_out_of_range_zero_cost(self):
        """Out of range = no IL accruing."""
        cost = il_cost_from_vol(sigma=0.60, dt_hours=1, position_value=100_000,
                               price=1000, price_lower=1500, price_upper=2500)
        assert cost == 0.0

    def test_narrower_range_higher_cost(self):
        """Narrower range has higher concentration factor, so higher IL cost."""
        cost_wide = il_cost_from_vol(sigma=0.60, dt_hours=1, position_value=100_000,
                                     price=2000, price_lower=1000, price_upper=4000)
        cost_narrow = il_cost_from_vol(sigma=0.60, dt_hours=1, position_value=100_000,
                                       price=2000, price_lower=1800, price_upper=2200)
        assert cost_narrow > cost_wide

    def test_reasonable_magnitude(self):
        """Sanity check: 60% vol, $100k position, 24h should be a few dollars."""
        cost = il_cost_from_vol(sigma=0.60, dt_hours=24, position_value=100_000,
                               price=2000, price_lower=1500, price_upper=2500)
        # With 60% vol, concentration ~1.29, 24h:
        # 0.5 * 1.29 * 0.36 * (24/8760) * 100000 ≈ $63
        assert 10 < cost < 500  # reasonable range
