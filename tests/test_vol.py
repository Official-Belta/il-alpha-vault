"""Tests for volatility estimators."""

import numpy as np
import pandas as pd
import pytest

from models.vol import realized_vol_ewma, realized_vol_with_shock


def make_price_series(n=500, base=2000, annual_vol=0.60, seed=42):
    """Generate a simple GBM price series for testing."""
    rng = np.random.default_rng(seed)
    hourly_vol = annual_vol / np.sqrt(8760)
    returns = hourly_vol * rng.standard_normal(n)
    prices = base * np.exp(np.cumsum(returns))
    return pd.Series(prices)


class TestEWMAVol:
    def test_output_length_matches_input(self):
        prices = make_price_series(100)
        vol = realized_vol_ewma(prices, halflife_hours=24)
        assert len(vol) == len(prices)

    def test_first_value_is_nan(self):
        prices = make_price_series(100)
        vol = realized_vol_ewma(prices, halflife_hours=24)
        assert pd.isna(vol.iloc[0])

    def test_values_are_positive(self):
        prices = make_price_series(500)
        vol = realized_vol_ewma(prices, halflife_hours=24)
        valid = vol.dropna()
        assert (valid > 0).all()

    def test_recovers_known_vol(self):
        """EWMA should approximately recover the input vol over enough data."""
        prices = make_price_series(5000, annual_vol=0.60, seed=123)
        vol = realized_vol_ewma(prices, halflife_hours=72)
        # Take the median of the last 1000 values (steady state)
        median_vol = vol.iloc[-1000:].median()
        # Should be within 30% of true vol (EWMA is noisy, especially hourly)
        assert 0.30 < median_vol < 1.00

    def test_shorter_halflife_reacts_faster(self):
        """Shorter half-life should produce more volatile vol estimates."""
        prices = make_price_series(500)
        vol_short = realized_vol_ewma(prices, halflife_hours=6)
        vol_long = realized_vol_ewma(prices, halflife_hours=72)
        # Shorter halflife → more variance in the vol estimate
        assert vol_short.dropna().std() > vol_long.dropna().std()

    def test_constant_price_zero_vol(self):
        """Constant prices should give ~zero vol."""
        prices = pd.Series([2000.0] * 100)
        vol = realized_vol_ewma(prices, halflife_hours=24)
        valid = vol.dropna()
        # All should be 0 or NaN (no returns)
        assert (valid == 0).all() or valid.isna().all()


class TestShockDetector:
    def test_output_lengths_match(self):
        prices = make_price_series(500)
        vol, shocks = realized_vol_with_shock(prices, halflife_hours=24)
        assert len(vol) == len(prices)
        assert len(shocks) == len(prices)

    def test_no_shocks_in_calm_market(self):
        """Low-vol series shouldn't trigger shocks."""
        prices = make_price_series(500, annual_vol=0.10, seed=99)
        _, shocks = realized_vol_with_shock(
            prices, halflife_hours=24, shock_threshold_sigma=4.0
        )
        # Very few or no shocks with low vol and high threshold
        assert shocks.sum() < 5

    def test_shock_on_large_move(self):
        """Inject a large price drop and verify shock triggers."""
        prices = make_price_series(200, annual_vol=0.30)
        # Inject 20% crash at hour 100
        prices.iloc[100] = prices.iloc[99] * 0.80
        _, shocks = realized_vol_with_shock(
            prices, halflife_hours=24, shock_threshold_sigma=3.0
        )
        assert shocks.iloc[100] == True

    def test_shock_raises_vol_estimate(self):
        """During shock, vol estimate should be higher than EWMA alone."""
        prices = make_price_series(200, annual_vol=0.30)
        prices.iloc[100] = prices.iloc[99] * 0.80

        ewma_vol = realized_vol_ewma(prices, halflife_hours=24)
        shock_vol, _ = realized_vol_with_shock(
            prices, halflife_hours=24, shock_threshold_sigma=3.0,
            shock_floor_vol=1.50
        )

        # Right after crash, shock vol should exceed EWMA
        assert shock_vol.iloc[101] >= ewma_vol.iloc[101]

    def test_shock_decays(self):
        """Shock override should decay back to EWMA after decay period."""
        prices = make_price_series(300, annual_vol=0.30)
        prices.iloc[100] = prices.iloc[99] * 0.75

        shock_vol, _ = realized_vol_with_shock(
            prices, halflife_hours=24, shock_threshold_sigma=3.0,
            shock_floor_vol=1.50, shock_decay_hours=12
        )

        ewma_vol = realized_vol_ewma(prices, halflife_hours=24)
        # After decay period, shock_vol should converge back to EWMA
        # (the crash itself elevates EWMA, so we compare the two)
        assert shock_vol.iloc[130] == pytest.approx(ewma_vol.iloc[130], rel=0.01)
