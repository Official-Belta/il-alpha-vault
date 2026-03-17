"""
Backtest performance metrics.

Computes PnL, Sharpe ratio, max drawdown, and comparison stats.
"""

import numpy as np
import pandas as pd


def total_return(equity_curve: pd.Series) -> float:
    """Total return as fraction (e.g., 0.15 = 15%)."""
    if len(equity_curve) < 2 or equity_curve.iloc[0] == 0:
        return 0.0
    return (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0


def sharpe_ratio(equity_curve: pd.Series, periods_per_year: float = 8760) -> float:
    """Annualized Sharpe ratio (assumes 0 risk-free rate).

    Args:
        equity_curve: Absolute equity values over time.
        periods_per_year: Number of periods per year (8760 for hourly).
    """
    returns = equity_curve.pct_change().dropna()
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    return returns.mean() / returns.std() * np.sqrt(periods_per_year)


def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum drawdown as a negative fraction (e.g., -0.20 = -20%)."""
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    return drawdown.min()


def summarize(
    strategy_equity: pd.Series,
    hodl_equity: pd.Series,
    always_lp_equity: pd.Series,
    signals: list,
) -> dict:
    """Produce a summary dict comparing strategy vs baselines."""
    n_active = sum(1 for s in signals if s.lp_active)
    n_total = len(signals)
    n_shocks = sum(1 for s in signals if s.shock)

    position_changes = 0
    for i in range(1, len(signals)):
        if signals[i].lp_active != signals[i - 1].lp_active:
            position_changes += 1

    return {
        "strategy_return": total_return(strategy_equity),
        "hodl_return": total_return(hodl_equity),
        "always_lp_return": total_return(always_lp_equity),
        "strategy_vs_hodl": total_return(strategy_equity) - total_return(hodl_equity),
        "strategy_vs_always_lp": total_return(strategy_equity) - total_return(always_lp_equity),
        "strategy_sharpe": sharpe_ratio(strategy_equity),
        "hodl_sharpe": sharpe_ratio(hodl_equity),
        "always_lp_sharpe": sharpe_ratio(always_lp_equity),
        "strategy_max_dd": max_drawdown(strategy_equity),
        "hodl_max_dd": max_drawdown(hodl_equity),
        "always_lp_max_dd": max_drawdown(always_lp_equity),
        "hours_in_lp": n_active,
        "hours_total": n_total,
        "pct_time_in_lp": n_active / n_total * 100 if n_total > 0 else 0,
        "position_changes": position_changes,
        "shocks_detected": n_shocks,
    }


def print_summary(summary: dict, label: str = "") -> None:
    """Pretty-print a backtest summary."""
    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

    print(f"\n  Returns:")
    print(f"    Strategy:    {summary['strategy_return']:+.2%}")
    print(f"    HODL:        {summary['hodl_return']:+.2%}")
    print(f"    Always LP:   {summary['always_lp_return']:+.2%}")
    print(f"    vs HODL:     {summary['strategy_vs_hodl']:+.2%}")
    print(f"    vs Always LP:{summary['strategy_vs_always_lp']:+.2%}")

    print(f"\n  Risk:")
    print(f"    Strategy Sharpe:  {summary['strategy_sharpe']:.2f}")
    print(f"    HODL Sharpe:      {summary['hodl_sharpe']:.2f}")
    print(f"    Always LP Sharpe: {summary['always_lp_sharpe']:.2f}")
    print(f"    Strategy Max DD:  {summary['strategy_max_dd']:.2%}")

    print(f"\n  Activity:")
    print(f"    Time in LP:       {summary['pct_time_in_lp']:.1f}% ({summary['hours_in_lp']}/{summary['hours_total']} hours)")
    print(f"    Position changes: {summary['position_changes']}")
    print(f"    Shocks detected:  {summary['shocks_detected']}")
