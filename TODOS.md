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

## Phase 2: Solidity V4 Hook + Vault

### P1 — Must Do

- [x] **V4 Solidity hook prototype** (`contracts/src/ILAlphaHook.sol`)
  - Direct IHooks implementation (no BaseTestHooks dependency)
  - afterSwap: EWMA vol oracle (packed 1-slot struct) + volume EWMA + LP toggle
  - Volume-aware fee yield: feeYield = fee_rate * ewmaVolume
  - 24h cooldown, lambda bounds [5000-9900], tick range validation
  - Two-step ownership transfer
  - Keeper functions: pushVolEstimate (uint128-capped), triggerEvaluation

- [x] **On-chain vol oracle** (EWMA, keeper-hybrid)
  - Packed VolOracle struct: uint128+int24+uint40+uint16 = 1 storage slot
  - Tick-squared returns, EWMA decay, time-normalized to per-hour
  - uint128 cap prevents overflow on extreme tick deltas

- [x] **ERC-4626 vault token** (`contracts/src/ILAlphaVault.sol`)
  - Solmate ERC4626 with virtual shares (1e6 offset) for inflation attack defense
  - Proper LiquidityAmounts math for two-sided LP deployment
  - Reentrancy guard on deposit/rebalance/emergencyWithdraw
  - Two-step ownership transfer
  - Emergency withdraw + pause

- [x] **Tests** (44 tests passing)
  - `test/ILAlphaHook.t.sol`: 28 tests — registration, vol oracle (incl. zero-elapsed, large delta), LP toggle (activate/deactivate/reactivate/cooldown), keeper, admin (ownership, lambda bounds, tick range), views
  - `test/ILAlphaVault.t.sol`: 16 tests — deposit/withdraw, virtual shares inflation defense, multi-depositor fairness, rebalance, emergency, access control, reentrancy

### P2 — Should Do

- [ ] CREATE2 address mining for hook deployment (permission flags in address)
- [ ] Rebalance integration test (deploy LP + remove LP full flow with actual V4 pool)

## Deferred (Phase 3+)

- [ ] **Formal security audit checklist**: Pre-mainnet review covering reentrancy analysis, overflow checks, access control review, ERC4626 compliance, V4 hook permission validation. Eng review identified 10+ items now fixed in code but a comprehensive audit pass is needed before mainnet. Start with OpenZeppelin's ERC4626 security checklist.

- [ ] **Gas benchmarks + optimization pass**: Profile afterSwap hot path (currently ~8-10K gas overhead per swap). Opportunities: remove VolUpdated event in production (saves ~1.5K), use EIP-1153 transient storage for vault callback state, batch SSTORE operations. Run `forge test --gas-report` for baseline.

- [ ] **Keeper bot implementation**: Python/JS bot that reads off-chain vol (from Binance data via `models/vol.py`), calls `pushVolEstimate()` + `triggerEvaluation()` periodically. Bridges Phase 1 Python to Phase 2 Solidity. Requires: RPC endpoint, funded EOA, cron/Gelato. Start from `data/fetch_binance.py` + `models/vol.py`.

- MEV defense (commit-reveal or auction)
- Multi-pool support
- Dynamic tick range adjustment
- Dashboard/visualization app
- Gas cost modeling (on-chain tx costs — slippage is now modeled in runner.py)
- **Dynamic fee share**: Replace fixed `fee_share` param with `position_liquidity / pool_liquidity` from pool data. Blocked by: real pool data from The Graph (synthetic liquidity is arbitrary). Start: `runner.py` line ~124, use `df["liquidity"]` column.
