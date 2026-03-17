"""Tests for backtest metrics — Sharpe, drawdown, total return."""

import numpy as np
import pandas as pd
import pytest

from backtest.metrics import max_drawdown, sharpe_ratio, total_return, summarize
from strategy.engine import Signal


class TestTotalReturn:
    def test_positive_return(self):
        equity = pd.Series([100, 110, 120])
        assert total_return(equity) == pytest.approx(0.20)

    def test_negative_return(self):
        equity = pd.Series([100, 90, 80])
        assert total_return(equity) == pytest.approx(-0.20)

    def test_flat(self):
        equity = pd.Series([100, 100, 100])
        assert total_return(equity) == pytest.approx(0.0)

    def test_empty(self):
        assert total_return(pd.Series([], dtype=float)) == 0.0

    def test_single_value(self):
        assert total_return(pd.Series([100])) == 0.0


class TestSharpeRatio:
    def test_constant_returns_zero_sharpe(self):
        """Constant equity (zero vol) → zero Sharpe."""
        equity = pd.Series([100] * 100)
        assert sharpe_ratio(equity) == 0.0

    def test_positive_sharpe(self):
        """Steadily increasing equity should have positive Sharpe."""
        equity = pd.Series(100 + np.arange(1000) * 0.01)
        assert sharpe_ratio(equity) > 0

    def test_too_short(self):
        assert sharpe_ratio(pd.Series([100])) == 0.0


class TestMaxDrawdown:
    def test_no_drawdown(self):
        """Monotonically increasing → zero drawdown."""
        equity = pd.Series([100, 110, 120, 130])
        assert max_drawdown(equity) == pytest.approx(0.0)

    def test_known_drawdown(self):
        """100 → 80 is a 20% drawdown."""
        equity = pd.Series([100, 80, 90])
        assert max_drawdown(equity) == pytest.approx(-0.20)

    def test_multiple_drawdowns(self):
        """Should report the worst one."""
        equity = pd.Series([100, 90, 95, 70, 80])
        assert max_drawdown(equity) == pytest.approx(-0.30)

    def test_empty(self):
        assert max_drawdown(pd.Series([], dtype=float)) == 0.0


class TestSummarize:
    def test_basic_summary(self):
        n = 100
        strategy = pd.Series(100 + np.arange(n) * 0.1)
        hodl = pd.Series(100 + np.arange(n) * 0.05)
        always_lp = pd.Series(100 + np.arange(n) * 0.08)

        signals = [
            Signal(timestamp=i, lp_active=(i % 3 != 0), fee_yield_ann=0.1,
                   il_cost_ann=0.05, edge=2.0, vol=0.6, price=2000)
            for i in range(n)
        ]

        summary = summarize(strategy, hodl, always_lp, signals)
        assert "strategy_return" in summary
        assert "hodl_return" in summary
        assert "strategy_sharpe" in summary
        assert "strategy_max_dd" in summary
        assert summary["hours_total"] == n
        assert summary["position_changes"] > 0
