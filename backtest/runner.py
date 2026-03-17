"""
Backtest simulation runner.

Simulates the fee-vs-IL strategy on historical (or synthetic) pool data.
Tracks three equity curves: strategy, HODL, and always-LP.

Usage:
    python -m backtest.runner --data data/raw/SYNTHETIC_ETH_USDC_005_2023-01-01_2024-01-01.csv
    python -m backtest.runner --data data/raw/SYNTHETIC_ETH_USDC_005_2023-01-01_2024-01-01.csv --vol-method shock
    python -m backtest.runner --data data/raw/SYNTHETIC_ETH_USDC_005_2023-01-01_2024-01-01.csv --compare
"""

import argparse
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.metrics import print_summary, summarize
from data.loader import load_pool_data
from models.fees import fee_yield_annualized, fees_earned_usdc, is_in_range
from models.il import il_cost_from_vol
from models.position import liquidity_from_deposit, position_value_usdc, token_amounts
from models.vol import realized_vol_ewma, realized_vol_with_shock
from strategy.engine import Signal, evaluate


def run_backtest(
    df: pd.DataFrame,
    deposit_usdc: float = 100_000.0,
    price_lower: float = 1200.0,
    price_upper: float = 3000.0,
    vol_method: str = "ewma",
    ewma_halflife: int = 24,
    shock_threshold: float = 3.0,
    shock_floor: float = 1.50,
    shock_decay: int = 12,
    fee_il_threshold: float = 1.0,
    fee_share: float = 0.001,
    slippage_bps: float = 10.0,
    cooldown_hours: int = 24,
) -> tuple[pd.DataFrame, list[Signal]]:
    """Run the backtest.

    Args:
        df: Pool hourly data (from loader).
        deposit_usdc: Initial deposit in USDC.
        price_lower: LP range lower bound.
        price_upper: LP range upper bound.
        vol_method: "ewma" or "shock".
        ewma_halflife: EWMA half-life in hours.
        shock_threshold: Shock detector sigma threshold.
        shock_floor: Shock detector vol floor.
        shock_decay: Shock detector decay hours.
        fee_il_threshold: Required fee/IL edge ratio.
        fee_share: Position's share of total pool fees (e.g., 0.001 = 0.1%).
        slippage_bps: Round-trip slippage cost in basis points per LP enter/exit (default 10 = 0.1%).
        cooldown_hours: Minimum hours between position changes to avoid churn (default 24).

    Returns:
        (results_df, signals) — full time series and signal list.
    """
    prices = df["eth_price_usd"]

    # --- Vol estimation ---
    if vol_method == "ewma":
        vol_series = realized_vol_ewma(prices, ewma_halflife)
        shock_series = pd.Series(False, index=df.index)
    elif vol_method == "shock":
        vol_series, shock_series = realized_vol_with_shock(
            prices, ewma_halflife, shock_threshold, shock_floor, shock_decay
        )
    else:
        raise ValueError(f"Unknown vol method: {vol_method}")

    # --- Initial position ---
    entry_price = prices.iloc[0]

    if entry_price <= price_lower or entry_price >= price_upper:
        can_deposit = False
    else:
        can_deposit = True

    if can_deposit:
        liquidity = liquidity_from_deposit(
            deposit_usdc, entry_price, price_lower, price_upper
        )
    else:
        liquidity = 0.0

    # --- Simulation state ---
    strategy_equity = np.zeros(len(df))
    hodl_equity = np.zeros(len(df))
    always_lp_equity = np.zeros(len(df))
    signals = []

    # HODL baseline: hold the initial token split at entry
    if can_deposit:
        init_usdc, init_eth = token_amounts(
            liquidity, entry_price, price_lower, price_upper
        )
    else:
        init_usdc = deposit_usdc
        init_eth = 0.0

    # Always-LP: same position, never withdraws
    always_lp_liquidity = liquidity if can_deposit else 0.0

    # Strategy state
    lp_active = can_deposit
    cumulative_fees_strategy = 0.0
    cumulative_fees_always = 0.0
    # When out of LP, track held token amounts
    held_usdc = 0.0
    held_eth = 0.0
    slippage_rate = slippage_bps / 10_000  # e.g., 10 bps = 0.001
    cumulative_slippage = 0.0
    hours_since_last_change = cooldown_hours  # allow immediate first action

    for i in range(len(df)):
        price = prices.iloc[i]
        vol = vol_series.iloc[i] if not pd.isna(vol_series.iloc[i]) else 0.0
        shock = bool(shock_series.iloc[i])
        pool_fees = df["feesUSD"].iloc[i]
        in_range = is_in_range(price, price_lower, price_upper)

        # --- Fee calculation ---
        # Hypothetical fees if in LP (used for signal, always computed)
        hypothetical_fees = pool_fees * fee_share if in_range else 0.0

        # Actual fees earned (only when LP is active)
        period_fees = hypothetical_fees if lp_active else 0.0

        if always_lp_liquidity > 0 and in_range:
            always_fees = pool_fees * fee_share
        else:
            always_fees = 0.0

        cumulative_fees_strategy += period_fees
        cumulative_fees_always += always_fees

        # --- Position values ---
        if liquidity > 0:
            lp_val = position_value_usdc(liquidity, price, price_lower, price_upper)
        else:
            lp_val = deposit_usdc

        hodl_val = init_usdc + init_eth * price

        if always_lp_liquidity > 0:
            always_lp_val = position_value_usdc(
                always_lp_liquidity, price, price_lower, price_upper
            )
        else:
            always_lp_val = deposit_usdc

        # --- Strategy equity ---
        if lp_active:
            strategy_equity[i] = lp_val + cumulative_fees_strategy
        else:
            # Out of LP: holding tokens received on withdrawal
            strategy_equity[i] = held_usdc + held_eth * price + cumulative_fees_strategy

        hodl_equity[i] = hodl_val
        always_lp_equity[i] = always_lp_val + cumulative_fees_always

        # --- IL cost estimate & fee yield for SIGNAL (always use hypothetical) ---
        # This is the expected fee/IL if we were in LP right now.
        # Used for the enter/exit decision, not for PnL accounting.
        if lp_val > 0:
            il_cost_usd = il_cost_from_vol(
                vol, dt_hours=1.0, position_value=lp_val,
                price=price, price_lower=price_lower, price_upper=price_upper
            )
            il_cost_ann = il_cost_usd / lp_val * 8760
        else:
            il_cost_usd = 0.0
            il_cost_ann = 0.0

        fee_ann = fee_yield_annualized(hypothetical_fees, lp_val, dt_hours=1.0) if lp_val > 0 else 0.0
        edge = fee_ann / il_cost_ann if il_cost_ann > 0 else float("inf")

        # --- Strategy decision for next period ---
        should_lp = evaluate(fee_ann, il_cost_ann, fee_il_threshold)
        if shock and vol_method == "shock":
            should_lp = False

        signal = Signal(
            timestamp=df["timestamp"].iloc[i],
            lp_active=lp_active,
            fee_yield_ann=fee_ann,
            il_cost_ann=il_cost_ann,
            edge=edge,
            vol=vol,
            price=price,
            shock=shock,
        )
        signals.append(signal)

        # --- State transitions (with slippage + cooldown) ---
        # Only allow state change if cooldown has elapsed
        can_change = hours_since_last_change >= cooldown_hours

        if can_change and lp_active and not should_lp:
            # Withdrawing: receive tokens from LP position, minus slippage
            raw_usdc, raw_eth = token_amounts(
                liquidity, price, price_lower, price_upper
            )
            slip_cost = (raw_usdc + raw_eth * price) * slippage_rate
            cumulative_slippage += slip_cost
            slip_frac = 1.0 - slippage_rate
            held_usdc = raw_usdc * slip_frac
            held_eth = raw_eth * slip_frac
            lp_active = False
            hours_since_last_change = 0
        elif can_change and not lp_active and should_lp and in_range:
            # Re-entering: deposit held tokens back into LP, minus slippage
            redeposit_value = held_usdc + held_eth * price
            slip_cost = redeposit_value * slippage_rate
            cumulative_slippage += slip_cost
            redeposit_value -= slip_cost
            if redeposit_value > 0:
                liquidity = liquidity_from_deposit(
                    redeposit_value, price, price_lower, price_upper
                )
            held_usdc = 0.0
            held_eth = 0.0
            lp_active = True
            hours_since_last_change = 0
        else:
            hours_since_last_change += 1

    # --- Build results DataFrame ---
    results = pd.DataFrame({
        "timestamp": df["timestamp"],
        "price": prices.values,
        "vol": vol_series.values,
        "strategy_equity": strategy_equity,
        "hodl_equity": hodl_equity,
        "always_lp_equity": always_lp_equity,
        "lp_active": [s.lp_active for s in signals],
        "fee_yield_ann": [s.fee_yield_ann for s in signals],
        "il_cost_ann": [s.il_cost_ann for s in signals],
        "edge": [s.edge for s in signals],
        "shock": [s.shock for s in signals],
    })

    return results, signals


def main():
    parser = argparse.ArgumentParser(description="Run IL Alpha Vault backtest")
    parser.add_argument("--data", required=True, help="Path to pool data CSV")
    parser.add_argument("--deposit", type=float, default=100_000, help="Deposit in USDC")
    parser.add_argument("--price-lower", type=float, default=1200, help="LP range lower")
    parser.add_argument("--price-upper", type=float, default=3000, help="LP range upper")
    parser.add_argument(
        "--vol-method", choices=["ewma", "shock"], default="ewma",
        help="Vol estimator method"
    )
    parser.add_argument("--halflife", type=int, default=24, help="EWMA half-life hours")
    parser.add_argument("--threshold", type=float, default=1.0, help="Fee/IL edge threshold")
    parser.add_argument("--fee-share", type=float, default=0.001, help="Position share of pool fees")
    parser.add_argument("--slippage-bps", type=float, default=10, help="Slippage cost in bps per enter/exit (default: 10)")
    parser.add_argument("--cooldown", type=int, default=24, help="Min hours between position changes (default: 24)")
    parser.add_argument("--compare", action="store_true", help="Run both methods and compare")
    parser.add_argument("--output", default=None, help="Save results CSV to path")
    args = parser.parse_args()

    df = load_pool_data(args.data)

    if args.compare:
        # Run both methods and compare
        for method in ["ewma", "shock"]:
            results, signals = run_backtest(
                df,
                deposit_usdc=args.deposit,
                price_lower=args.price_lower,
                price_upper=args.price_upper,
                vol_method=method,
                ewma_halflife=args.halflife,
                fee_il_threshold=args.threshold,
                fee_share=args.fee_share,
                slippage_bps=args.slippage_bps,
                cooldown_hours=args.cooldown,
            )
            summary = summarize(
                pd.Series(results["strategy_equity"]),
                pd.Series(results["hodl_equity"]),
                pd.Series(results["always_lp_equity"]),
                signals,
            )
            print_summary(summary, label=f"Vol Method: {method.upper()}")

            if args.output:
                out_path = Path(args.output).with_suffix(f".{method}.csv")
                results.to_csv(out_path, index=False)
                print(f"\n  Results saved to {out_path}")
    else:
        results, signals = run_backtest(
            df,
            deposit_usdc=args.deposit,
            price_lower=args.price_lower,
            price_upper=args.price_upper,
            vol_method=args.vol_method,
            ewma_halflife=args.halflife,
            fee_il_threshold=args.threshold,
            fee_share=args.fee_share,
            slippage_bps=args.slippage_bps,
        )
        summary = summarize(
            pd.Series(results["strategy_equity"]),
            pd.Series(results["hodl_equity"]),
            pd.Series(results["always_lp_equity"]),
            signals,
        )
        print_summary(summary, label=f"Vol Method: {args.vol_method.upper()}")

        if args.output:
            results.to_csv(args.output, index=False)
            print(f"\n  Results saved to {args.output}")


if __name__ == "__main__":
    main()
