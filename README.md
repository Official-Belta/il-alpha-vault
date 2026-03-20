# IL Alpha

**Treasury-grade LP management on Uniswap V4.** Removes LP positions before impermanent loss hits.

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)

---

## What it does

IL Alpha is a Uniswap V4 hook that makes one decision every hour:

```
fee_yield > IL_cost → LP stays active (earning fees)
fee_yield < IL_cost → LP removed entirely (capital preserved)
```

Every other LP manager (Arrakis, Gamma, Charm) keeps LP active during volatility — adjusting ranges or fees. IL Alpha removes LP entirely when expected value is negative.

## Why it matters

- **49.5%** of Uniswap LPs lose more to IL than they earn in fees
- **$24.5B** in DAO treasuries sit idle because LP = IL risk
- **IL Alpha:** Sharpe 3.66, Max Drawdown -12% (vs -45% for always-on LP)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Uniswap V4 │◄────│ ILAlphaHook  │────►│    Keeper     │
│  PoolManager│     │ (afterSwap)  │     │  (1hr cycle)  │
│  Singleton  │     │ EWMA Oracle  │     │               │
└──────┬──────┘     └──────┬───────┘     └───────────────┘
       │                   │
       │            ┌──────▼───────┐
       └────────────│ ILAlphaVault │
                    │  (ERC-4626)  │
                    └──────────────┘
```

**Contracts:**
- `ILAlphaHook.sol` — V4 hook with on-chain EWMA volatility oracle
- `ILAlphaVault.sol` — ERC-4626 vault with real-time LP valuation + TWAP protection
- `BaseVault.sol` — Shared base with virtual shares (inflation attack prevention)
- `AlwaysLPVault.sol` / `HODLVault.sol` — Control groups for A/B comparison

## Backtest Results (2-Year Real ETH/USDC Data)

| Metric | IL Alpha | AlwaysLP | HODL |
|--------|----------|----------|------|
| **Sharpe Ratio** | **3.66** | 3.24 | 1.11 |
| **Max Drawdown** | **-12%** | -45% | -65% |
| Return | +231% | +297% | +91% |

IL Alpha sacrifices 22% raw return for 73% reduction in worst-case drawdown.

## Security

- 4-round internal security audit: **0 Critical, 0 High**
- Real-time LP valuation (not stale accounting)
- TWAP check on deposit/withdraw (sandwich protection)
- Virtual shares (ERC-4626 inflation attack prevention)
- Volume spike trigger (emergency LP removal)
- Public `rebalance()` fallback (no single point of failure)

**Status: UNAUDITED by professional firm. Seeking UFSF audit subsidy.**

## Tech Stack

- **Solidity** — Foundry, Uniswap V4 hooks
- **Python** — Backtesting, keeper bot
- **65** Solidity tests (incl. fuzz) | **99** Python tests

## Quick Start

```bash
# Contracts
cd contracts
forge install
forge build
forge test

# Backtest
pip install -r requirements.txt
python -m backtest.runner --data data/raw/ETH_USDC.csv
```

## Links

- [Milestone Site](https://official-belta.github.io/il-alpha-site/)
- [Investment Thesis](https://official-belta.github.io/il-alpha-site/thesis.html)
- [Competitive Analysis](docs/COMPETITIVE.md)
- [Roadmap](docs/ROADMAP.md)
- [Messaging & Positioning](docs/MESSAGING.md)

## License

MIT
