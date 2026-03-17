# TODOS

## Phase 1: Python Backtest (Scope Reduction — prove the thesis)

### P1 — Must Do

- [x] **Acquire historical Uniswap pool data**
  - Synthetic data generator with GBM, vol regimes, flash crashes (`data/generate_synthetic.py`)
  - Subgraph fetcher ready for real data (`data/fetch_pool_data.py`, needs GRAPH_API_KEY)
  - Unified loader with validation (`data/loader.py`)
  - Still need: real data from The Graph or Dune when API key available

- [x] **Port BELTA functions to Python**
  - `models/position.py`: token_amounts, position_value_usdc, liquidity_from_deposit
  - `models/il.py`: il_full_range, il_concentrated, il_cost_from_vol (gamma exposure model)
  - `models/fees.py`: fees_earned_usdc, fee_yield_annualized
  - Unit tests with all canonical IL values verified (2x=5.72%, 4x=20%, symmetry)

- [x] **Implement vol estimators + comparative backtest**
  - `models/vol.py`: EWMA + shock detector (3-sigma circuit breaker with decay)
  - `strategy/engine.py`: fee/IL edge signal
  - `backtest/runner.py`: full simulation with HODL and always-LP baselines
  - `backtest/metrics.py`: Sharpe, max drawdown, return attribution
  - 99 tests passing. Thesis confirmed on synthetic data.
  - Finding: shock detector has marginal PnL impact (~2-5% less LP time).
    EWMA alone is sufficient for Phase 2. Shock detector adds complexity for minimal benefit.

### P2 — Should Do

- [x] **Jupyter notebook: IL-as-gamma-exposure derivation**
  - `notebooks/il_alpha_vault.ipynb` — 15 cells, 6 charts
  - Math: IL formula derivation, gamma exposure model, concentration factor
  - Charts: IL curve, IL cost vs vol, concentrated IL comparison, vol estimators,
    equity curves (4-panel), sensitivity analysis (4-panel)
  - Executes cleanly end-to-end on synthetic data

## Deferred (Phase 2+)

- V4 Solidity hook prototype
- On-chain vol oracle (TWAP-based)
- MEV defense (commit-reveal or auction)
- ERC-4626 vault token
- Keeper/automation layer (Chainlink/Gelato)
- Multi-pool support
- Dynamic tick range adjustment
- Dashboard/visualization app
- Gas cost modeling (on-chain tx costs — slippage is now modeled in runner.py)
- **Dynamic fee share**: Replace fixed `fee_share` param with `position_liquidity / pool_liquidity` from pool data. Blocked by: real pool data from The Graph (synthetic liquidity is arbitrary). Start: `runner.py` line ~124, use `df["liquidity"]` column.
