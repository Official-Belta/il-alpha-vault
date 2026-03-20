# IL Alpha — Auditor Brief

**Date:** 2026-03-21
**Repo:** https://github.com/Official-Belta/il-alpha-vault
**Commit:** ff9b40b
**Contact:** [CEO/Eng contact info]

---

## 1. What Is This?

A Uniswap V4 hook + ERC-4626 vault that **turns LP off during high volatility** to avoid impermanent loss. When vol drops, it turns LP back on to earn fees.

```
                  ┌──────────────┐
  Depositors ───→ │ ILAlphaVault │ ──→ deposit USDC, receive shares
                  │  (ERC-4626)  │
                  └──────┬───────┘
                         │ rebalance()
                         ▼
                  ┌──────────────┐
                  │  PoolManager │ ──→ add/remove LP
                  │   (V4 core)  │
                  └──────┬───────┘
                         │ afterSwap()
                         ▼
                  ┌──────────────┐
                  │ ILAlphaHook  │ ──→ EWMA vol oracle + LP on/off signal
                  │              │
                  └──────────────┘
                         ↑
                      Keeper bot
                  (off-chain, pushes vol)
```

---

## 2. Audit Scope (3 files, ~650 LOC)

| File | LOC | Purpose |
|------|-----|---------|
| `contracts/src/ILAlphaHook.sol` | ~500 | V4 afterSwap hook: EWMA vol oracle, LP toggle, volume spike detection, tick TWAP accumulator |
| `contracts/src/ILAlphaVault.sol` | ~490 | ERC-4626 vault: deposit/withdraw, real-time LP valuation, TWAP manipulation check, slippage protection |
| `contracts/src/BaseVault.sol` | ~55 | Abstract ERC-4626 with virtual shares (inflation attack defense) |

**Out of scope:**
- `contracts/src/controls/` — benchmark vaults (no real funds)
- `contracts/src/SwapHelper.sol` — testnet helper only
- `contracts/script/` — deployment scripts
- `keeper/` — off-chain Python bot

---

## 3. Key Mechanisms

### Vol Oracle (ILAlphaHook)
- EWMA of tick-squared returns, packed in 1 storage slot (uint128+int24+uint40+uint16)
- Updated every swap via `afterSwap`
- Keeper can blend off-chain vol estimate via `pushVolEstimate` (rate-limited to 2x)
- Volume spike detection: single swap > 3x EWMA volume → emergency LP off (bypasses cooldown)

### LP Toggle
- `feeYield = poolFee × ewmaVolume / 1M`
- `ilCost = 0.5 × ewmaVar × concentration / 1e36`
- If `feeYield > ilCost` → LP on; else LP off
- 24-hour cooldown between toggles

### TWAP (ILAlphaHook)
- 10-observation circular buffer, recency-weighted
- Per-block deduplication (prevents same-block buffer flooding)
- Vault checks spot tick vs TWAP tick on deposit/withdraw; reverts if deviation > threshold

### Vault Accounting
- `totalAssets()` = idle balance + real-time LP value (asset token only)
- LP value from `LiquidityAmounts.getAmountsForLiquidity()` — not stale storage
- Virtual shares offset (1e6) for first-depositor inflation defense
- No withdrawal fee (intentionally removed — caused ERC-4626 spec violations in prior iterations)

### Access Control
- Two-step ownership transfer (both hook and vault)
- Keeper role on hook (pushVol, triggerEvaluation)
- Keeper address on vault (informational, no modifier — rebalance is public)
- All admin setters: zero-address checks, bounds validation, event emission

---

## 4. Prior Internal Audit (4 rounds)

We conducted 4 rounds of internal audit using Trail of Bits methodology:

| Round | Findings | Critical | High | Status |
|-------|----------|----------|------|--------|
| V1 | 38 | 4 | 8 | All fixed |
| V2 | 11 | 0 | 2 | All fixed (fee removed) |
| V3 | 10 | 0 | 0 | M-1 fixed, rest accepted |
| V4 | 9 | 0 | 0 | All fixed except 2 Phase 4 |

Full reports: `docs/audit/` → `v2/` → `v3/` → `v4/`

### Known Accepted Items (Phase 4)
1. **50/50 asset split for LP** — vault holds single token, splits for two-sided LP. Pre-swap not yet implemented.
2. **TWAP is recency-weighted** — not true time-weighted average. Falls back to lastTick when no valid observations.

---

## 5. Trust Assumptions

| Actor | Trust Level | Can Do | Cannot Do |
|-------|-------------|--------|-----------|
| Owner | High (will be multi-sig) | Pause, emergency withdraw, change params | Steal depositor funds directly |
| Keeper | Medium | Push vol estimates (2x rate limited), trigger evaluation | Drain vault, bypass deposit cap |
| Depositor | Untrusted | Deposit, withdraw, call rebalance | Manipulate share price (TWAP check) |
| PoolManager | Trusted (Uniswap V4) | Execute swaps, manage liquidity | N/A |

---

## 6. Areas of Concern

We'd like the auditor to focus on:

1. **ERC-4626 compliance** — all 9 functions (deposit, mint, withdraw, redeem, convertTo*, preview*, max*). We removed withdrawal fee after it broke compliance 3 times.
2. **Share price manipulation** — `totalAssets()` uses `slot0` for LP valuation. TWAP check mitigates but may be insufficient.
3. **Slippage check** — per-token comparison for cross-decimal pairs (USDC 6 vs WETH 18). Is the approach correct?
4. **TWAP oracle** — 10 observations, recency-weighted, per-block dedup. Is this sufficient for L2?
5. **Reentrancy** — vault interacts with PoolManager via unlock callback. `nonReentrant` on deposit/withdraw/rebalance/emergency.
6. **Vol oracle gaming** — can an attacker slowly manipulate EWMA to force LP on/off at will?

---

## 7. Build & Test

```bash
cd contracts
forge build
forge test -vvv          # 71 tests, all passing
forge test --gas-report  # gas benchmarks
```

### Dependencies
- Solidity 0.8.26
- Foundry (forge, cast)
- Uniswap v4-core (submodule in lib/)
- Solmate ERC4626/ERC20

---

## 8. Deployment Plan

- **Chain:** Arbitrum mainnet (also Base later)
- **Deposit cap:** $10,000 USDC (hard limit)
- **Owner:** Gnosis Safe multi-sig (post-deploy transfer)
- **Keeper:** Separate EOA, pushes Binance EWMA vol hourly
- **Seed:** $1K CEO funds (Phase A), +$10K genesis depositor (Phase B)

---

## 9. File Map

```
contracts/src/
├── ILAlphaHook.sol     # AUDIT TARGET — V4 hook
├── ILAlphaVault.sol    # AUDIT TARGET — ERC-4626 vault
├── BaseVault.sol       # AUDIT TARGET — virtual shares base
├── SwapHelper.sol      # out of scope (testnet)
└── controls/           # out of scope (benchmark)

contracts/test/
├── ILAlphaHook.t.sol   # 31 tests (fuzz included)
├── ILAlphaVault.t.sol  # 33 tests (fuzz included)
└── ControlVaults.t.sol # 7 tests
```
