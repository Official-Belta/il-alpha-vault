"""
Generate realistic synthetic Uniswap V3 pool hourly data for pipeline testing.

Simulates ETH/USDC-like pool with:
- Geometric Brownian Motion price dynamics with vol regimes
- Volume correlated with volatility (more vol = more trading)
- Fees as a function of volume and fee tier
- Liquidity that drifts slowly with TVL changes
- Occasional flash crashes to test shock detection

Usage:
    python -m data.generate_synthetic --start 2023-01-01 --end 2024-01-01
    python -m data.generate_synthetic --start 2023-01-01 --end 2024-01-01 --crash-count 3
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def generate_vol_regimes(n_hours: int, rng: np.random.Generator) -> np.ndarray:
    """Generate a time series of hourly volatility with regime switching.

    Regimes: low (~30% annualized), medium (~60%), high (~100%).
    Transitions happen randomly every few days.
    """
    annualized_vols = [0.30, 0.60, 1.00]
    regime_durations_hours = [72, 48, 24]  # avg hours per regime

    vols = np.zeros(n_hours)
    i = 0
    while i < n_hours:
        regime = rng.choice(3, p=[0.5, 0.35, 0.15])
        duration = int(rng.exponential(regime_durations_hours[regime]))
        duration = max(duration, 6)
        end = min(i + duration, n_hours)
        # Hourly vol = annualized / sqrt(8760)
        hourly_vol = annualized_vols[regime] / np.sqrt(8760)
        vols[i:end] = hourly_vol
        i = end

    return vols


def inject_crashes(
    prices: np.ndarray, n_crashes: int, rng: np.random.Generator
) -> np.ndarray:
    """Inject sudden price drops (flash crashes) into the price series."""
    n = len(prices)
    if n_crashes == 0:
        return prices

    crash_indices = rng.choice(range(n // 10, n - n // 10), size=n_crashes, replace=False)
    for idx in sorted(crash_indices):
        drop_pct = rng.uniform(0.10, 0.30)  # 10-30% drop
        recovery_hours = int(rng.uniform(6, 48))
        # Sudden drop
        prices[idx] *= (1 - drop_pct)
        # Partial recovery over next hours
        recovery_target = prices[idx] / (1 - drop_pct) * (1 - drop_pct * 0.3)
        for j in range(1, min(recovery_hours, n - idx)):
            frac = j / recovery_hours
            prices[idx + j] = prices[idx] + (recovery_target - prices[idx]) * frac

    return prices


def generate(
    start_date: str,
    end_date: str,
    initial_price: float = 1600.0,
    fee_tier_bps: int = 5,
    initial_tvl: float = 200_000_000.0,
    crash_count: int = 2,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    n_hours = int((end - start).total_seconds() / 3600)

    if n_hours <= 0:
        raise ValueError(f"End date must be after start date (got {n_hours} hours)")

    timestamps = pd.date_range(start=start, periods=n_hours, freq="h", tz="UTC")

    # --- Price simulation (GBM with vol regimes) ---
    hourly_vols = generate_vol_regimes(n_hours, rng)
    # Small positive drift (ETH trending up slightly over the year)
    hourly_drift = 0.0001

    log_returns = hourly_drift + hourly_vols * rng.standard_normal(n_hours)
    log_prices = np.log(initial_price) + np.cumsum(log_returns)
    prices = np.exp(log_prices)

    prices = inject_crashes(prices, crash_count, rng)

    # OHLC from close prices with some noise
    close = prices
    noise = rng.uniform(0.995, 1.005, n_hours)
    open_ = np.roll(close, 1) * noise
    open_[0] = initial_price
    high = np.maximum(open_, close) * rng.uniform(1.0, 1.005, n_hours)
    low = np.minimum(open_, close) * rng.uniform(0.995, 1.0, n_hours)

    # --- Volume: correlated with volatility ---
    # Base daily volume ~$500M for ETH/USDC 0.05%, so hourly ~$20M
    base_hourly_volume = 20_000_000.0
    # Higher vol = more volume (vol traders + arb)
    annualized_vols_series = hourly_vols * np.sqrt(8760)
    vol_multiplier = annualized_vols_series / 0.30  # normalize to low-vol baseline
    volume_noise = rng.lognormal(0, 0.3, n_hours)
    volume_usd = base_hourly_volume * vol_multiplier * volume_noise

    # --- Fees: volume * fee_tier ---
    fee_rate = fee_tier_bps / 1_000_000  # 5 bps = 0.00005
    fees_usd = volume_usd * fee_rate

    # --- Liquidity: slow random walk around initial TVL ---
    tvl_log_returns = rng.normal(0, 0.001, n_hours)  # very slow drift
    tvl = initial_tvl * np.exp(np.cumsum(tvl_log_returns))
    # Liquidity in V3 terms (arbitrary but consistent scale)
    liquidity = tvl * 1e12 / prices

    # --- Fee growth globals (cumulative, monotonically increasing) ---
    # Simplified: just cumulative fees scaled to X128 format
    fee_growth_0 = np.cumsum(fees_usd * 0.5 / tvl) * (2**128)
    fee_growth_1 = np.cumsum(fees_usd * 0.5 / tvl) * (2**128)

    # --- Tick from price ---
    # tick = log(price) / log(1.0001) for Uniswap V3
    tick = np.floor(np.log(prices) / np.log(1.0001)).astype(int)

    # --- Tx count: correlated with volume ---
    tx_count = (volume_usd / 50_000 * rng.uniform(0.5, 1.5, n_hours)).astype(int)

    # token0Price = USDC in WETH terms = 1/eth_price
    # token1Price = WETH in USDC terms = eth_price
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "liquidity": liquidity,
            "sqrtPrice": np.sqrt(prices) * (2**96),  # sqrtPriceX96 format
            "token0Price": 1.0 / prices,
            "token1Price": prices,
            "tick": tick,
            "feeGrowthGlobal0X128": fee_growth_0,
            "feeGrowthGlobal1X128": fee_growth_1,
            "tvlUSD": tvl,
            "volumeUSD": volume_usd,
            "feesUSD": fees_usd,
            "txCount": tx_count,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "eth_price_usd": prices,
        }
    )

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic Uniswap V3 pool data"
    )
    parser.add_argument("--start", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-01-01", help="End date (YYYY-MM-DD)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--crash-count", type=int, default=2, help="Number of flash crashes to inject"
    )
    parser.add_argument("--output-dir", default="data/raw", help="Output directory")
    args = parser.parse_args()

    print(f"Generating synthetic ETH/USDC 0.05% pool data")
    print(f"  Period: {args.start} to {args.end}")
    print(f"  Seed: {args.seed}, crashes: {args.crash_count}")

    df = generate(args.start, args.end, crash_count=args.crash_count, seed=args.seed)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"SYNTHETIC_ETH_USDC_005_{args.start}_{args.end}.csv"
    out_path = out_dir / filename
    df.to_csv(out_path, index=False)

    print(f"\nSaved to {out_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  ETH price range: ${df['eth_price_usd'].min():.2f} - ${df['eth_price_usd'].max():.2f}")
    print(f"  Total fees: ${df['feesUSD'].sum():,.2f}")
    print(f"  Total volume: ${df['volumeUSD'].sum():,.2f}")
    print(f"  Vol regimes visible: check price chart for regime switches")


if __name__ == "__main__":
    main()
