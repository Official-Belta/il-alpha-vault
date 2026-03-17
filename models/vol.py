"""
Realized volatility estimators.

Two methods for the comparative backtest:

1. EWMA (Exponentially Weighted Moving Average)
   - Standard in options market-making
   - Single parameter: half-life (in hours)
   - Reacts smoothly to vol changes, but lags on sudden spikes

2. EWMA + Shock Detector
   - Same EWMA baseline, plus a circuit breaker
   - If price moves > k*sigma in one period, flag as "shock"
   - During shock: override vol estimate to a high floor value
   - Two parameters: EWMA half-life + shock threshold (k sigma)

Both output annualized volatility at each timestep.
"""

import numpy as np
import pandas as pd


def realized_vol_ewma(
    prices: pd.Series,
    halflife_hours: int = 24,
) -> pd.Series:
    """EWMA realized volatility estimator.

    Computes log returns, then exponentially weighted variance,
    annualized to get sigma.

    Args:
        prices: Hourly price series (must be > 0, no NaNs).
        halflife_hours: EWMA half-life in hours. Shorter = faster reaction.

    Returns:
        Annualized vol series (same index as prices, first value is NaN).
    """
    log_returns = np.log(prices / prices.shift(1))

    # EWMA variance of log returns
    ewma_var = log_returns.ewm(halflife=halflife_hours, min_periods=2).var()

    # Annualize: hourly variance * 8760 hours/year, then sqrt
    annualized_vol = np.sqrt(ewma_var * 8760)

    return annualized_vol


def realized_vol_with_shock(
    prices: pd.Series,
    halflife_hours: int = 24,
    shock_threshold_sigma: float = 3.0,
    shock_floor_vol: float = 1.50,
    shock_decay_hours: int = 12,
) -> tuple[pd.Series, pd.Series]:
    """EWMA vol with shock detector circuit breaker.

    Uses EWMA as baseline. When a single-period return exceeds
    shock_threshold_sigma * current_vol, overrides the estimate
    with a floor value that decays back to EWMA over shock_decay_hours.

    Args:
        prices: Hourly price series.
        halflife_hours: EWMA half-life in hours.
        shock_threshold_sigma: Trigger threshold in sigma units.
        shock_floor_vol: Annualized vol floor during shock (e.g., 1.50 = 150%).
        shock_decay_hours: Hours for shock override to decay back to EWMA.

    Returns:
        (vol_series, shock_flags) — annualized vol and boolean shock indicators.
    """
    ewma_vol = realized_vol_ewma(prices, halflife_hours)
    log_returns = np.log(prices / prices.shift(1))

    vol_out = ewma_vol.copy()
    shock_flags = pd.Series(False, index=prices.index)

    # Hourly vol from annualized
    hourly_ewma = ewma_vol / np.sqrt(8760)

    shock_remaining = 0  # hours of shock override remaining

    for i in range(1, len(prices)):
        ret = abs(log_returns.iloc[i])
        h_vol = hourly_ewma.iloc[i]

        if pd.isna(h_vol) or h_vol <= 0:
            continue

        # Check for shock
        if ret > shock_threshold_sigma * h_vol:
            shock_remaining = shock_decay_hours
            shock_flags.iloc[i] = True

        # Apply shock override with linear decay
        if shock_remaining > 0:
            decay_frac = shock_remaining / shock_decay_hours
            shock_vol = shock_floor_vol * decay_frac
            vol_out.iloc[i] = max(ewma_vol.iloc[i], shock_vol)
            shock_remaining -= 1

    return vol_out, shock_flags
