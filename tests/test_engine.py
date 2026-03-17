"""Tests for strategy engine — the LP enter/exit decision logic."""

import pytest

from strategy.engine import Signal, evaluate


class TestEvaluate:
    def test_positive_edge_activates_lp(self):
        """When fees > IL cost, LP should be active."""
        assert evaluate(fee_yield_ann=0.50, il_cost_ann=0.20, threshold=1.0) is True

    def test_negative_edge_deactivates_lp(self):
        """When fees < IL cost, LP should be inactive."""
        assert evaluate(fee_yield_ann=0.10, il_cost_ann=0.50, threshold=1.0) is False

    def test_exact_breakeven_is_not_active(self):
        """At exactly threshold, edge is not strictly greater — should be inactive."""
        assert evaluate(fee_yield_ann=0.50, il_cost_ann=0.50, threshold=1.0) is False

    def test_zero_il_cost_always_active(self):
        """Zero IL cost = free money, always LP."""
        assert evaluate(fee_yield_ann=0.10, il_cost_ann=0.0) is True

    def test_negative_il_cost_always_active(self):
        """Negative IL cost = free money, always LP."""
        assert evaluate(fee_yield_ann=0.10, il_cost_ann=-0.01) is True

    def test_zero_fees_never_active(self):
        """Zero fees with positive IL cost = never LP."""
        assert evaluate(fee_yield_ann=0.0, il_cost_ann=0.10) is False

    def test_threshold_margin_of_safety(self):
        """With threshold=1.2, need 20% more fees than IL to activate."""
        # edge = 0.30 / 0.20 = 1.5 > 1.2 → active
        assert evaluate(fee_yield_ann=0.30, il_cost_ann=0.20, threshold=1.2) is True
        # edge = 0.24 / 0.20 = 1.2, not strictly > 1.2 → inactive
        assert evaluate(fee_yield_ann=0.24, il_cost_ann=0.20, threshold=1.2) is False

    def test_both_zero(self):
        """Both zero: il_cost <= 0, so always LP."""
        assert evaluate(fee_yield_ann=0.0, il_cost_ann=0.0) is True


class TestSignal:
    def test_construction(self):
        sig = Signal(
            timestamp="2023-01-01",
            lp_active=True,
            fee_yield_ann=0.25,
            il_cost_ann=0.10,
            edge=2.5,
            vol=0.60,
            price=2000.0,
        )
        assert sig.lp_active is True
        assert sig.shock is False  # default

    def test_shock_flag(self):
        sig = Signal(
            timestamp="2023-01-01",
            lp_active=False,
            fee_yield_ann=0.0,
            il_cost_ann=0.0,
            edge=0.0,
            vol=1.50,
            price=1800.0,
            shock=True,
        )
        assert sig.shock is True
