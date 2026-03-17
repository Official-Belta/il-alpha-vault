"""
Fetch historical Uniswap V3 pool data from The Graph subgraph.

Pulls poolHourData for a given pool: price, fees, liquidity, volume per hour.
Saves to CSV for backtest consumption.

Usage:
    python -m data.fetch_pool_data --pool ETH_USDC_005 --start 2023-01-01 --end 2024-01-01
    python -m data.fetch_pool_data --pool ETH_USDC_030 --start 2023-01-01 --end 2024-01-01

Requires GRAPH_API_KEY env var (free at https://thegraph.com/studio/).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# Uniswap V3 subgraph on The Graph decentralized network
SUBGRAPH_ID = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"

# Well-known pool addresses
POOLS = {
    "ETH_USDC_005": {
        "address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "name": "ETH/USDC 0.05%",
        "fee_tier": 500,
        "token0": "USDC",
        "token1": "WETH",
    },
    "ETH_USDC_030": {
        "address": "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8",
        "name": "ETH/USDC 0.3%",
        "fee_tier": 3000,
        "token0": "USDC",
        "token1": "WETH",
    },
}

QUERY_POOL_HOUR_DATA = """
query PoolHourData($pool: String!, $startTime: Int!, $skip: Int!) {
  poolHourDatas(
    first: 1000
    skip: $skip
    orderBy: periodStartUnix
    orderDirection: asc
    where: { pool: $pool, periodStartUnix_gte: $startTime }
  ) {
    periodStartUnix
    liquidity
    sqrtPrice
    token0Price
    token1Price
    tick
    feeGrowthGlobal0X128
    feeGrowthGlobal1X128
    tvlUSD
    volumeUSD
    feesUSD
    txCount
    open
    high
    low
    close
  }
}
"""


def get_api_url() -> str:
    api_key = os.environ.get("GRAPH_API_KEY")
    if not api_key:
        print("Error: GRAPH_API_KEY env var not set.")
        print("Get a free key at https://thegraph.com/studio/")
        print("Then: export GRAPH_API_KEY=your_key_here")
        sys.exit(1)
    return f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{SUBGRAPH_ID}"


def fetch_pool_hour_data(
    pool_address: str, start_ts: int, end_ts: int
) -> list[dict]:
    url = get_api_url()
    all_data = []
    skip = 0
    page_size = 1000

    while True:
        variables = {
            "pool": pool_address,
            "startTime": start_ts,
            "skip": skip,
        }

        resp = requests.post(
            url,
            json={"query": QUERY_POOL_HOUR_DATA, "variables": variables},
            timeout=30,
        )
        resp.raise_for_status()

        result = resp.json()
        if "errors" in result:
            print(f"GraphQL errors: {json.dumps(result['errors'], indent=2)}")
            sys.exit(1)

        records = result["data"]["poolHourDatas"]
        if not records:
            break

        # Filter by end timestamp
        for r in records:
            if int(r["periodStartUnix"]) <= end_ts:
                all_data.append(r)

        if int(records[-1]["periodStartUnix"]) > end_ts:
            break

        if len(records) < page_size:
            break

        skip += page_size
        print(f"  Fetched {len(all_data)} hours so far...")
        time.sleep(0.5)  # rate limit courtesy

    return all_data


def to_dataframe(raw_data: list[dict], pool_info: dict) -> pd.DataFrame:
    df = pd.DataFrame(raw_data)

    df["timestamp"] = pd.to_datetime(
        df["periodStartUnix"].astype(int), unit="s", utc=True
    )
    df["liquidity"] = df["liquidity"].astype(float)
    df["sqrtPrice"] = df["sqrtPrice"].astype(float)
    df["token0Price"] = df["token0Price"].astype(float)
    df["token1Price"] = df["token1Price"].astype(float)
    df["tick"] = df["tick"].astype(int)
    df["tvlUSD"] = df["tvlUSD"].astype(float)
    df["volumeUSD"] = df["volumeUSD"].astype(float)
    df["feesUSD"] = df["feesUSD"].astype(float)
    df["txCount"] = df["txCount"].astype(int)
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    df["feeGrowthGlobal0X128"] = df["feeGrowthGlobal0X128"].astype(float)
    df["feeGrowthGlobal1X128"] = df["feeGrowthGlobal1X128"].astype(float)

    # Derive ETH price in USD (token1 is WETH, token0 is USDC)
    # token0Price = price of token0 in terms of token1 (USDC per WETH? No.)
    # In Uniswap V3 subgraph: token0Price = price of token0 denominated in token1
    # For USDC/WETH pool: token0Price = USDC price in WETH, token1Price = WETH price in USDC
    df["eth_price_usd"] = df["token1Price"]

    df = df.sort_values("timestamp").reset_index(drop=True)

    # Drop raw unix timestamp column
    df = df.drop(columns=["periodStartUnix"])

    return df


def validate(df: pd.DataFrame) -> None:
    issues = []

    if df.empty:
        print("Error: Dataset is empty. Check your date range and pool address.")
        sys.exit(1)

    nan_cols = df.columns[df.isna().any()].tolist()
    if nan_cols:
        issues.append(f"NaN values in columns: {nan_cols}")

    zero_prices = (df["eth_price_usd"] <= 0).sum()
    if zero_prices > 0:
        issues.append(f"{zero_prices} rows with zero/negative ETH price")

    neg_fees = (df["feesUSD"] < 0).sum()
    if neg_fees > 0:
        issues.append(f"{neg_fees} rows with negative fees")

    # Check timestamps are monotonically increasing
    if not df["timestamp"].is_monotonic_increasing:
        issues.append("Timestamps not monotonically increasing")

    if issues:
        print("Validation warnings:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Validation passed.")


def main():
    parser = argparse.ArgumentParser(description="Fetch Uniswap V3 pool hour data")
    parser.add_argument(
        "--pool",
        choices=list(POOLS.keys()),
        default="ETH_USDC_005",
        help="Pool to fetch (default: ETH_USDC_005)",
    )
    parser.add_argument(
        "--start", required=True, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", required=True, help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="Output directory (default: data/raw)",
    )
    args = parser.parse_args()

    pool_info = POOLS[args.pool]
    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    print(f"Fetching {pool_info['name']} hourly data")
    print(f"  Period: {args.start} to {args.end}")
    print(f"  Pool: {pool_info['address']}")

    raw_data = fetch_pool_hour_data(pool_info["address"], start_ts, end_ts)
    print(f"  Total hours fetched: {len(raw_data)}")

    if not raw_data:
        print("No data returned. Check your date range and API key.")
        sys.exit(1)

    df = to_dataframe(raw_data, pool_info)
    validate(df)

    # Save
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{args.pool}_{args.start}_{args.end}.csv"
    out_path = out_dir / filename
    df.to_csv(out_path, index=False)

    print(f"\nSaved to {out_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  ETH price range: ${df['eth_price_usd'].min():.2f} - ${df['eth_price_usd'].max():.2f}")
    print(f"  Total fees: ${df['feesUSD'].sum():,.2f}")
    print(f"  Total volume: ${df['volumeUSD'].sum():,.2f}")


if __name__ == "__main__":
    main()
