"""
Fetch historical ETH hourly data from Binance free API.

No API key required. Unlimited historical data.
Produces pool-compatible CSV with fee estimation for backtest.

Usage:
    python -m data.fetch_binance --start 2024-01-01 --end 2026-03-17
"""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BINANCE_API = "https://api.binance.com/api/v3/klines"
SYMBOL = "ETHUSDT"
FEE_RATE = 0.0005  # Uniswap 0.05% pool


def fetch_klines(start_ms: int, end_ms: int) -> list:
    """Fetch all hourly klines between start and end timestamps."""
    all_data = []
    cursor = start_ms

    while cursor < end_ms:
        params = {
            "symbol": SYMBOL,
            "interval": "1h",
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1000,
        }
        resp = requests.get(BINANCE_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        all_data.extend(data)
        # Move cursor past the last candle
        cursor = data[-1][0] + 3600000  # +1 hour in ms
        print(f"  Fetched {len(all_data)} hours...")

        if len(data) < 1000:
            break

        time.sleep(0.2)

    return all_data


def to_pool_dataframe(klines: list) -> pd.DataFrame:
    """Convert Binance klines to pool-compatible DataFrame.

    Binance kline format:
    [open_time, open, high, low, close, volume, close_time,
     quote_volume, trades, taker_buy_base, taker_buy_quote, ignore]
    """
    records = []
    for k in klines:
        ts = int(k[0]) // 1000  # ms to seconds
        open_p = float(k[1])
        high_p = float(k[2])
        low_p = float(k[3])
        close_p = float(k[4])
        volume_eth = float(k[5])
        quote_volume = float(k[7])  # volume in USDT
        trades = int(k[8])

        records.append({
            "timestamp_unix": ts,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "eth_price_usd": close_p,
            "volumeUSD": quote_volume,
            "txCount": trades,
        })

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp_unix"], unit="s", utc=True)

    # Estimate Uniswap pool fields
    # Fee = volume * fee_rate (Uniswap 0.05% pool captures ~30-50% of CEX volume)
    # We use a scaling factor: Uniswap ETH/USDC 0.05% pool typically does
    # ~5-15% of Binance ETH/USDT volume
    uniswap_volume_ratio = 0.10  # conservative estimate
    df["volumeUSD"] = df["volumeUSD"] * uniswap_volume_ratio
    df["feesUSD"] = df["volumeUSD"] * FEE_RATE

    # Estimate TVL from volume (Uniswap ETH/USDC 0.05% TVL ~$200-500M)
    # Use rolling 24h volume * 20 as rough TVL proxy
    rolling_vol = df["volumeUSD"].rolling(24, min_periods=1).sum()
    df["tvlUSD"] = rolling_vol.clip(lower=50_000_000) * 20
    df["liquidity"] = df["tvlUSD"] * 1e12 / df["eth_price_usd"]

    # Technical fields
    df["sqrtPrice"] = np.sqrt(df["eth_price_usd"]) * (2**96)
    df["token0Price"] = 1.0 / df["eth_price_usd"]
    df["token1Price"] = df["eth_price_usd"]
    df["tick"] = np.floor(np.log(df["eth_price_usd"]) / np.log(1.0001)).astype(int)
    df["feeGrowthGlobal0X128"] = 0.0
    df["feeGrowthGlobal1X128"] = 0.0

    df = df.drop(columns=["timestamp_unix"])
    return df


def main():
    parser = argparse.ArgumentParser(description="Fetch ETH historical data from Binance")
    parser.add_argument("--start", default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-03-17", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default="data/raw", help="Output directory")
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    print(f"Fetching ETH/USDT hourly data from Binance")
    print(f"  Period: {args.start} to {args.end}")

    klines = fetch_klines(start_ms, end_ms)
    print(f"  Total candles: {len(klines)}")

    df = to_pool_dataframe(klines)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"BINANCE_ETH_USDC_{args.start}_{args.end}.csv"
    out_path = out_dir / filename
    df.to_csv(out_path, index=False)

    print(f"\nSaved to {out_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  ETH price range: ${df['eth_price_usd'].min():.2f} - ${df['eth_price_usd'].max():.2f}")
    print(f"  Est. pool fees: ${df['feesUSD'].sum():,.2f}")
    print(f"  Est. pool volume: ${df['volumeUSD'].sum():,.2f}")


if __name__ == "__main__":
    main()
