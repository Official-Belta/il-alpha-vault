"""
Unified data loader for backtest pipeline.

Handles:
  - Synthetic generated data
  - CSV imports (Dune Analytics exports, manual downloads)
  - The Graph subgraph (when API key available)

All sources produce the same DataFrame schema:
  timestamp, eth_price_usd, volumeUSD, feesUSD, tvlUSD, liquidity,
  open, high, low, close, tick, sqrtPrice,
  feeGrowthGlobal0X128, feeGrowthGlobal1X128, token0Price, token1Price, txCount

Usage:
    from data.loader import load_pool_data
    df = load_pool_data("data/raw/SYNTHETIC_ETH_USDC_005_2023-01-01_2024-01-01.csv")
"""

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "timestamp",
    "eth_price_usd",
    "volumeUSD",
    "feesUSD",
    "tvlUSD",
    "liquidity",
]


def load_pool_data(path: str | Path) -> pd.DataFrame:
    """Load pool hourly data from CSV and validate."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(f"Dataset is empty: {path}")

    # Check required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    # Parse timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Ensure numeric types
    for col in ["eth_price_usd", "volumeUSD", "feesUSD", "tvlUSD", "liquidity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Validate
    nan_count = df[REQUIRED_COLUMNS].isna().sum().sum()
    if nan_count > 0:
        nan_detail = df[REQUIRED_COLUMNS].isna().sum()
        nan_detail = nan_detail[nan_detail > 0]
        raise ValueError(f"NaN values found after parsing:\n{nan_detail}")

    zero_prices = (df["eth_price_usd"] <= 0).sum()
    if zero_prices > 0:
        raise ValueError(f"{zero_prices} rows with zero/negative ETH price")

    neg_fees = (df["feesUSD"] < 0).sum()
    if neg_fees > 0:
        raise ValueError(f"{neg_fees} rows with negative fees")

    if not df["timestamp"].is_monotonic_increasing:
        df = df.sort_values("timestamp").reset_index(drop=True)

    print(f"Loaded {len(df)} rows from {path.name}")
    print(f"  {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  ETH price: ${df['eth_price_usd'].min():.2f} - ${df['eth_price_usd'].max():.2f}")

    return df
