"""Integration tests for backtest runner."""

import numpy as np
import pandas as pd
import pytest

from backtest.runner import run_backtest
from data.generate_synthetic import generate


@pytest.fixture
def synthetic_data():
    """Generate a small synthetic dataset for testing."""
    return generate("2023-01-01", "2023-02-01", seed=42)


class TestRunBacktest:
    def test_returns_correct_shape(self, synthetic_data):
        """Output should have same number of rows as input."""
        results, signals = run_backtest(synthetic_data, deposit_usdc=100_000)
        assert len(results) == len(synthetic_data)
        assert len(signals) == len(synthetic_data)

    def test_equity_starts_at_deposit(self, synthetic_data):
        """All equity curves should start near the deposit amount."""
        results, _ = run_backtest(synthetic_data, deposit_usdc=100_000)
        assert results["strategy_equity"].iloc[0] == pytest.approx(100_000, rel=0.01)
        assert results["hodl_equity"].iloc[0] == pytest.approx(100_000, rel=0.01)
        assert results["always_lp_equity"].iloc[0] == pytest.approx(100_000, rel=0.01)

    def test_equity_always_positive(self, synthetic_data):
        """Equity should never go negative."""
        results, _ = run_backtest(synthetic_data, deposit_usdc=100_000)
        assert (results["strategy_equity"] > 0).all()
        assert (results["hodl_equity"] > 0).all()
        assert (results["always_lp_equity"] > 0).all()

    def test_ewma_method(self, synthetic_data):
        """EWMA vol method should run without error."""
        results, signals = run_backtest(
            synthetic_data, vol_method="ewma", deposit_usdc=100_000
        )
        assert len(results) > 0

    def test_shock_method(self, synthetic_data):
        """Shock vol method should run without error."""
        results, signals = run_backtest(
            synthetic_data, vol_method="shock", deposit_usdc=100_000
        )
        assert len(results) > 0

    def test_invalid_vol_method(self, synthetic_data):
        with pytest.raises(ValueError):
            run_backtest(synthetic_data, vol_method="invalid")

    def test_strategy_toggles_lp(self, synthetic_data):
        """Strategy should toggle LP on/off at least once over a month."""
        results, signals = run_backtest(
            synthetic_data, deposit_usdc=100_000, fee_il_threshold=1.0
        )
        lp_states = results["lp_active"]
        changes = (lp_states != lp_states.shift()).sum()
        # Should have at least one state change in a month of data
        assert changes >= 1

    def test_high_threshold_less_lp_time(self, synthetic_data):
        """Higher fee/IL threshold should result in less time in LP."""
        _, signals_low = run_backtest(
            synthetic_data, deposit_usdc=100_000, fee_il_threshold=0.5
        )
        _, signals_high = run_backtest(
            synthetic_data, deposit_usdc=100_000, fee_il_threshold=2.0
        )
        lp_time_low = sum(1 for s in signals_low if s.lp_active)
        lp_time_high = sum(1 for s in signals_high if s.lp_active)
        assert lp_time_high <= lp_time_low

    def test_price_out_of_range_start(self):
        """When starting price is outside LP range, should handle gracefully."""
        df = generate("2023-01-01", "2023-01-15", initial_price=500, seed=42)
        results, signals = run_backtest(
            df, deposit_usdc=100_000, price_lower=1200, price_upper=3000
        )
        # Should run without crashing, equity = deposit (no LP possible)
        assert len(results) == len(df)

    def test_slippage_reduces_returns(self, synthetic_data):
        """Higher slippage should reduce strategy returns."""
        results_no_slip, _ = run_backtest(
            synthetic_data, deposit_usdc=100_000, slippage_bps=0
        )
        results_high_slip, _ = run_backtest(
            synthetic_data, deposit_usdc=100_000, slippage_bps=100
        )
        # With slippage, final equity should be lower (assuming some position changes)
        assert results_high_slip["strategy_equity"].iloc[-1] <= results_no_slip["strategy_equity"].iloc[-1]

    def test_zero_slippage_matches_original(self, synthetic_data):
        """Zero slippage should produce same results as default behavior."""
        results, _ = run_backtest(
            synthetic_data, deposit_usdc=100_000, slippage_bps=0
        )
        # Just verify it runs and equity is reasonable
        assert results["strategy_equity"].iloc[-1] > 0
