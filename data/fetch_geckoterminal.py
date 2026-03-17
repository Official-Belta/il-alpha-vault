"""
Fetch real Uniswap V3 ETH/USDC 0.05% pool hourly data from GeckoTerminal.

Free API, no key required. Limited to last 180 days.
OHLCV + volume only — fees estimated as volume * fee_rate.

Usage:
    python -m data.fetch_geckoterminal
    python -m data.fetch_geckoterminal --days 90
"""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

POOL_ADDRESS = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
NETWORK = "eth"
FEE_RATE = 0.0005  # 5 bps = 0.05%
API_BASE = "https://api.geckoterminal.com/api/v2"


def fetch_ohlcv(before_timestamp: int, limit: int = 1000) -> list:
    """Fetch hourly OHLCV data from GeckoTerminal."""
    url = (
        f"{API_BASE}/networks/{NETWORK}/pools/{POOL_ADDRESS}"
        f"/ohlcv/hour?aggregate=1&limit={limit}"
        f"&before_timestamp={before_timestamp}&currency=usd"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise RuntimeError(f"API error: {data['errors']}")

    return data["data"]["attributes"]["ohlcv_list"]


def fetch_all(days: int = 170) -> pd.DataFrame:
    """Fetch all available hourly data by paginating backwards."""
    now = int(datetime.now(timezone.utc).timestamp())
    all_records = []
    cursor = now
    min_ts = now - (days * 86400)

    print(f"Fetching ~{days} days of hourly data for ETH/USDC 0.05%...")

    while cursor > min_ts:
        records = fetch_ohlcv(cursor, limit=1000)
        if not records:
            break

        all_records.extend(records)
        # Move cursor to before the oldest record
        oldest_ts = min(r[0] for r in records)
        cursor = oldest_ts
        print(f"  Fetched {len(all_records)} hours (back to {datetime.fromtimestamp(oldest_ts, tz=timezone.utc).strftime('%Y-%m-%d')})")

        if len(records) < 1000:
            break

        time.sleep(1.0)  # rate limit

    # Deduplicate by timestamp
    seen = set()
    unique = []
    for r in all_records:
        if r[0] not in seen:
            seen.add(r[0])
            unique.append(r)

    # Sort by timestamp ascending
    unique.sort(key=lambda x: x[0])

    # Filter to requested range
    unique = [r for r in unique if r[0] >= min_ts]

    df = pd.DataFrame(unique, columns=["timestamp_unix", "open", "high", "low", "close", "volumeUSD"])

    df["timestamp"] = pd.to_datetime(df["timestamp_unix"], unit="s", utc=True)
    df["eth_price_usd"] = df["close"]
    df["feesUSD"] = df["volumeUSD"] * FEE_RATE
    df["tvlUSD"] = np.nan  # Not available from this API
    df["liquidity"] = np.nan  # Not available from this API

    # Estimate TVL from volume (rough: daily volume ~ 5-10% of TVL for active pools)
    # Use rolling 24h volume * 15 as TVL estimate
    rolling_vol_24h = df["volumeUSD"].rolling(24, min_periods=1).sum()
    df["tvlUSD"] = rolling_vol_24h * 15
    df["liquidity"] = df["tvlUSD"] * 1e12 / df["eth_price_usd"]

    # Add fields expected by loader
    df["sqrtPrice"] = np.sqrt(df["eth_price_usd"]) * (2**96)
    df["token0Price"] = 1.0 / df["eth_price_usd"]
    df["token1Price"] = df["eth_price_usd"]
    df["tick"] = np.floor(np.log(df["eth_price_usd"]) / np.log(1.0001)).astype(int)
    df["feeGrowthGlobal0X128"] = 0.0
    df["feeGrowthGlobal1X128"] = 0.0
    df["txCount"] = (df["volumeUSD"] / 5000).astype(int).clip(lower=1)

    # Drop helper column
    df = df.drop(columns=["timestamp_unix"])

    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch real ETH/USDC pool data from GeckoTerminal")
    parser.add_argument("--days", type=int, default=170, help="Days of data to fetch (max ~180)")
    parser.add_argument("--output-dir", default="data/raw", help="Output directory")
    args = parser.parse_args()

    df = fetch_all(days=args.days)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    start_date = df["timestamp"].min().strftime("%Y-%m-%d")
    end_date = df["timestamp"].max().strftime("%Y-%m-%d")
    filename = f"REAL_ETH_USDC_005_{start_date}_{end_date}.csv"
    out_path = out_dir / filename
    df.to_csv(out_path, index=False)

    print(f"\nSaved to {out_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Date range: {start_date} to {end_date}")
    print(f"  ETH price range: ${df['eth_price_usd'].min():.2f} - ${df['eth_price_usd'].max():.2f}")
    print(f"  Total fees: ${df['feesUSD'].sum():,.2f}")
    print(f"  Total volume: ${df['volumeUSD'].sum():,.2f}")


if __name__ == "__main__":
    main()
