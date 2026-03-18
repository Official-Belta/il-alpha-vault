"""
IL Alpha Vault Keeper Bot

Bridges off-chain vol estimation (Phase 1 Python) to on-chain hook (Phase 2 Solidity).
Periodically:
  1. Fetches latest price data from Binance
  2. Computes EWMA variance using models/vol.py
  3. Calls hook.pushVolEstimate() with the computed variance
  4. Calls hook.triggerEvaluation() to re-evaluate LP toggle
  5. Calls vault.rebalance() to deploy/withdraw LP based on hook signal

Usage:
  python keeper/keeper.py --rpc-url <RPC_URL> --private-key <KEY> --pool-key <POOL_KEY_JSON>

Architecture:
  ┌─────────────┐    fetch     ┌──────────────┐
  │   Binance   │ ──────────→ │  EWMA Vol    │
  │   API       │              │  (models/)   │
  └─────────────┘              └──────┬───────┘
                                      │ variance
                                      ▼
  ┌─────────────┐  pushVol    ┌──────────────┐
  │  ILAlpha    │ ←────────── │   Keeper     │
  │  Hook       │  triggerEval│   Bot        │
  └──────┬──────┘              └──────┬───────┘
         │ isLPActive()               │ rebalance()
         ▼                            ▼
  ┌─────────────┐              ┌──────────────┐
  │  Pool       │              │  ILAlpha     │
  │  Manager    │              │  Vault       │
  └─────────────┘              └──────────────┘
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path for models/ imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.vol import EwmaEstimator
from data.fetch_binance import fetch_binance_klines

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("keeper")

# ─── ABI fragments for contract calls ────────────────────────────────

HOOK_ABI = [
    {
        "inputs": [
            {"components": [
                {"name": "currency0", "type": "address"},
                {"name": "currency1", "type": "address"},
                {"name": "fee", "type": "uint24"},
                {"name": "tickSpacing", "type": "int24"},
                {"name": "hooks", "type": "address"},
            ], "name": "key", "type": "tuple"},
            {"name": "externalVar", "type": "uint256"},
        ],
        "name": "pushVolEstimate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"components": [
                {"name": "currency0", "type": "address"},
                {"name": "currency1", "type": "address"},
                {"name": "fee", "type": "uint24"},
                {"name": "tickSpacing", "type": "int24"},
                {"name": "hooks", "type": "address"},
            ], "name": "key", "type": "tuple"},
        ],
        "name": "triggerEvaluation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"components": [
                {"name": "currency0", "type": "address"},
                {"name": "currency1", "type": "address"},
                {"name": "fee", "type": "uint24"},
                {"name": "tickSpacing", "type": "int24"},
                {"name": "hooks", "type": "address"},
            ], "name": "key", "type": "tuple"},
        ],
        "name": "isLPActive",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"components": [
                {"name": "currency0", "type": "address"},
                {"name": "currency1", "type": "address"},
                {"name": "fee", "type": "uint24"},
                {"name": "tickSpacing", "type": "int24"},
                {"name": "hooks", "type": "address"},
            ], "name": "key", "type": "tuple"},
        ],
        "name": "getVolEstimate",
        "outputs": [
            {"name": "hourlyVar", "type": "uint128"},
            {"name": "annualizedVol", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

VAULT_ABI = [
    {
        "inputs": [],
        "name": "rebalance",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getVaultMetrics",
        "outputs": [
            {"name": "totalAssetsVal", "type": "uint256"},
            {"name": "idleAssets", "type": "uint256"},
            {"name": "deployedAssetsVal", "type": "uint256"},
            {"name": "deployedLiquidityVal", "type": "uint128"},
            {"name": "sharePrice", "type": "uint256"},
            {"name": "lpActive", "type": "bool"},
            {"name": "isPaused", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def compute_tick_variance(prices: list[float], lambda_: float = 0.94) -> int:
    """
    Compute EWMA variance in tick-squared-per-hour units, matching on-chain format.

    The on-chain hook tracks variance as: tick_delta^2 * 1e18, time-normalized to per-hour.
    Off-chain, we compute the same from price log-returns:
      log_return ≈ tick_delta * ln(1.0001)
      tick_delta ≈ log_return / ln(1.0001)

    Returns variance scaled to 1e18 (uint256 compatible).
    """
    import math

    if len(prices) < 2:
        return 0

    LN_1_0001 = math.log(1.0001)

    # Compute EWMA variance of tick-space returns
    estimator = EwmaEstimator(lambda_=lambda_)
    for i in range(1, len(prices)):
        if prices[i - 1] <= 0:
            continue
        log_return = math.log(prices[i] / prices[i - 1])
        tick_delta = log_return / LN_1_0001
        estimator.update(tick_delta)

    # Scale to 1e18 and convert to int (matching Solidity PRECISION)
    variance = estimator.variance
    scaled = int(variance * 1e18)
    return min(scaled, 2**128 - 1)  # cap to uint128


def run_keeper_cycle(
    w3,
    hook_contract,
    vault_contract,
    pool_key_tuple: tuple,
    symbol: str = "ETHUSDC",
):
    """Execute one keeper cycle: fetch vol → push → trigger → rebalance."""

    # 1. Fetch recent hourly prices from Binance
    log.info(f"Fetching recent prices for {symbol}...")
    try:
        klines = fetch_binance_klines(
            symbol=symbol,
            interval="1h",
            limit=168,  # 7 days of hourly data
        )
        prices = [float(k[4]) for k in klines]  # close prices
        log.info(f"Got {len(prices)} hourly candles, latest price: ${prices[-1]:,.2f}")
    except Exception as e:
        log.error(f"Failed to fetch prices: {e}")
        return

    # 2. Compute EWMA variance
    variance = compute_tick_variance(prices)
    log.info(f"Computed tick variance: {variance} (scaled 1e18)")

    # 3. Read current on-chain state
    try:
        on_chain_var, annualized = hook_contract.functions.getVolEstimate(pool_key_tuple).call()
        is_active = hook_contract.functions.isLPActive(pool_key_tuple).call()
        log.info(f"On-chain: ewmaVar={on_chain_var}, annualized={annualized}, LP active={is_active}")
    except Exception as e:
        log.warning(f"Failed to read on-chain state: {e}")

    # 4. Push vol estimate
    log.info("Pushing vol estimate to hook...")
    try:
        tx = hook_contract.functions.pushVolEstimate(pool_key_tuple, variance)
        tx_hash = _send_tx(w3, tx)
        log.info(f"pushVolEstimate tx: {tx_hash}")
    except Exception as e:
        log.error(f"pushVolEstimate failed: {e}")
        return

    # 5. Trigger evaluation
    log.info("Triggering LP evaluation...")
    try:
        tx = hook_contract.functions.triggerEvaluation(pool_key_tuple)
        tx_hash = _send_tx(w3, tx)
        log.info(f"triggerEvaluation tx: {tx_hash}")
    except Exception as e:
        if "CooldownActive" in str(e):
            log.info("Cooldown active, skipping evaluation (normal)")
        else:
            log.error(f"triggerEvaluation failed: {e}")

    # 6. Rebalance vault
    log.info("Rebalancing vault...")
    try:
        tx = vault_contract.functions.rebalance()
        tx_hash = _send_tx(w3, tx)
        log.info(f"rebalance tx: {tx_hash}")
    except Exception as e:
        log.error(f"rebalance failed: {e}")

    # 7. Report vault metrics
    try:
        metrics = vault_contract.functions.getVaultMetrics().call()
        log.info(
            f"Vault metrics: totalAssets={metrics[0]}, idle={metrics[1]}, "
            f"deployed={metrics[2]}, liquidity={metrics[3]}, "
            f"sharePrice={metrics[4]}, lpActive={metrics[5]}, paused={metrics[6]}"
        )
    except Exception as e:
        log.warning(f"Failed to read vault metrics: {e}")


def _send_tx(w3, tx_func):
    """Build, sign, and send a transaction."""
    account = w3.eth.default_account
    tx = tx_func.build_transaction({
        "from": account,
        "nonce": w3.eth.get_transaction_count(account),
        "gas": 500_000,
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
    })
    private_key = os.environ.get("KEEPER_PRIVATE_KEY", "")
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt.status != 1:
        raise Exception(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


def main():
    parser = argparse.ArgumentParser(description="IL Alpha Vault Keeper Bot")
    parser.add_argument("--rpc-url", required=True, help="JSON-RPC endpoint")
    parser.add_argument("--hook-address", required=True, help="ILAlphaHook contract address")
    parser.add_argument("--vault-address", required=True, help="ILAlphaVault contract address")
    parser.add_argument("--pool-key", required=True, help="JSON file with pool key params")
    parser.add_argument("--symbol", default="ETHUSDC", help="Binance trading pair symbol")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between keeper cycles")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    # Setup web3
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(args.rpc_url))
    if not w3.is_connected():
        log.error(f"Cannot connect to {args.rpc_url}")
        sys.exit(1)

    private_key = os.environ.get("KEEPER_PRIVATE_KEY")
    if not private_key:
        log.error("KEEPER_PRIVATE_KEY environment variable not set")
        sys.exit(1)

    account = w3.eth.account.from_key(private_key)
    w3.eth.default_account = account.address
    log.info(f"Keeper address: {account.address}")
    log.info(f"Balance: {w3.from_wei(w3.eth.get_balance(account.address), 'ether')} ETH")

    # Load contracts
    hook_contract = w3.eth.contract(
        address=w3.to_checksum_address(args.hook_address),
        abi=HOOK_ABI,
    )
    vault_contract = w3.eth.contract(
        address=w3.to_checksum_address(args.vault_address),
        abi=VAULT_ABI,
    )

    # Load pool key
    with open(args.pool_key) as f:
        pk = json.load(f)
    pool_key_tuple = (
        w3.to_checksum_address(pk["currency0"]),
        w3.to_checksum_address(pk["currency1"]),
        pk["fee"],
        pk["tickSpacing"],
        w3.to_checksum_address(pk["hooks"]),
    )

    log.info(f"Hook: {args.hook_address}")
    log.info(f"Vault: {args.vault_address}")
    log.info(f"Pool: fee={pk['fee']}, tickSpacing={pk['tickSpacing']}")
    log.info(f"Interval: {args.interval}s")

    # Run loop
    while True:
        try:
            run_keeper_cycle(w3, hook_contract, vault_contract, pool_key_tuple, args.symbol)
        except Exception as e:
            log.error(f"Keeper cycle failed: {e}", exc_info=True)

        if args.once:
            break

        log.info(f"Sleeping {args.interval}s until next cycle...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
