# v2 Differential Security Review

**Date:** 2026-03-20
**Scope:** All changes across commits `19c7a63..8be8a26` (3 commits)
**Files changed:** ILAlphaHook.sol, ILAlphaVault.sol, SwapHelper.sol, AlwaysLPVault.sol

---

## 1. Fix-by-Fix Analysis

### H-1: TWAP Oracle (ILAlphaHook + ILAlphaVault)

**What changed:**
- Added `TickObservation` struct and circular buffer (`tickObservations[10]`, `observationIndex`) to ILAlphaHook
- `_recordTickObservation()` called in `afterSwap()` to store `(tick, timestamp)` per swap
- `getTwapTick()` computes recency-weighted average of observations within 1-hour window
- `_checkTWAP()` in ILAlphaVault now calls `hook.getTwapTick(poolId)` instead of using raw `lastTick`

**Correctness:** PARTIALLY CORRECT with caveats

**Issue 1 -- Fresh pool / all-zero timestamps:**
When `getTwapTick()` is called on a fresh pool (no swaps yet or all observations older than 1 hour), `totalWeight == 0` and it falls back to `volOracles[poolId].lastTick`. This is the same single-point-of-truth the fix was meant to replace. An attacker who manipulates price and waits >1 hour has no TWAP protection -- the fallback is just the last observed tick, which may itself be stale or manipulated.

- **Severity:** MEDIUM. The fallback degrades to v1 behavior, not worse. But it defeats the purpose of H-1 for low-activity pools.
- **Recommendation:** Consider returning a sentinel value or reverting when insufficient observations exist, rather than silently falling back.

**Issue 2 -- TWAP window is swap-count-based, not time-based:**
The buffer stores at most 10 observations. In high-frequency pools, all 10 could be from the same block (though same-block vol updates are skipped, TWAP observations are NOT skipped -- `_recordTickObservation` has no `elapsed == 0` guard). An attacker executing 10+ swaps in a single block could fill the entire buffer with a manipulated tick.

- **Severity:** HIGH. The TWAP can be fully corrupted within a single block by filling the 10-slot buffer with manipulated ticks.
- **Recommendation:** Add a minimum time gap between observations (e.g., skip if `block.timestamp == tickObservations[poolId][prevIdx].timestamp`).

**Issue 3 -- int24 truncation in weighted average:**
`twapTick = int24(int256(weightedSum / int256(totalWeight)))` -- the division result could theoretically exceed int24 range if `weightedSum` is very large and `totalWeight` is very small. In practice tick values are bounded by `[-887272, 887272]`, so the weighted average of valid ticks stays in int24 range. This is safe.

**Blast radius:** Moderate. Affects all deposit/withdraw/redeem paths that call `_checkTWAP()`, plus any external consumer of `getTwapTick()`.

---

### H-2: Slippage Check on LP Operations (ILAlphaVault)

**What changed:**
- Added `maxSlippageBps` (default 100 = 1%) and `SlippageExceeded` error
- `_checkSlippage()` computes `actualCost = sum of negative deltas` vs `maxCost = expected + expected * slippage`
- Called AFTER `_settleDelta(delta)` in `_executeAddLiquidity()`

**Correctness:** FUNCTIONALLY CORRECT but architecturally suboptimal

**Issue 1 -- Check is AFTER modifyLiquidity + settleDelta:**
By the time `_checkSlippage()` runs, tokens have ALREADY been transferred to PoolManager via `_settleDelta()`. The revert does unwind the entire unlock callback transaction (since it's all within `poolManager.unlock()`), so funds are NOT lost. The Uniswap V4 PoolManager treats the entire `unlock` callback as an atomic operation -- if it reverts, all state changes including pool modifications and token transfers are rolled back.

- **Severity:** LOW (informational). The revert correctly prevents fund loss. However, gas is wasted on the settlement before reverting.
- **Recommendation:** Acceptable pattern for V4 callbacks. Moving the check before settlement is not possible since you need the delta to check against.

**Issue 2 -- Slippage only checked on addLiquidity, not removeLiquidity:**
`_executeRemoveLiquidity()` calls `_settleDelta(delta)` but never calls `_checkSlippage()`. A manipulated pool could return fewer tokens than expected during removal.

- **Severity:** MEDIUM. Remove-side slippage is unprotected.
- **Recommendation:** Add slippage check to `_executeRemoveLiquidity()` as well, comparing returned amounts against expected value from `_getDeployedLPValue()`.

**Issue 3 -- `expected` parameter semantics:**
`_checkSlippage` receives the raw `assets` amount (the full idle balance), but the actual LP operation only uses `assets/2` per side (50/50 split). The check compares total negative deltas against the FULL asset amount + slippage. This means the effective slippage tolerance is ~2x what `maxSlippageBps` suggests, since the pool typically only consumes ~half of `assets` in each token.

- **Severity:** LOW. The slippage bound is looser than documented but still functional.

**Blast radius:** Limited to rebalance path. Withdrawals that trigger `_ensureIdle` -> `_removeLiquidity` are unprotected.

---

### H-7: Cross-Token Valuation Fix (ILAlphaVault.totalAssets)

**What changed:**
- v1: `return idle + lpValue0 + lpValue1` (summed both token values as if 1:1)
- v2: Only counts the LP value in the vault's asset token, ignoring the other side

**Correctness:** CORRECT (conservative)

This is a sound fix. The v1 approach assumed 1:1 cross-token pricing which would inflate totalAssets for non-stablecoin pairs. The v2 approach understates totalAssets when the LP holds the non-asset token, which is safe -- it means share price is lower than true value, preventing share-price inflation attacks.

**Edge case -- single-sided LP outside range:**
If the pool price moves such that the entire LP position is in the non-asset token (e.g., price moves far above the LP range when asset is token0), then `lpValue0 == 0` and `totalAssets == idle`. This causes share price to drop to reflect only idle assets, which could trigger underpriced withdrawals. However, this is a known trade-off documented in the code and is strictly safer than overvaluation.

**Blast radius:** Affects ALL share price calculations (deposit, withdraw, redeem, convertToShares, convertToAssets).

---

### H-6: AlwaysLPVault Double-Counting Fix

**What changed:**
- Removed `deployedAssets` state variable entirely
- `totalAssets()` now returns only `asset.balanceOf(address(this))`
- `rebalance()` is a no-op that just emits an event
- Removed `beforeWithdraw` override that was zeroing `deployedAssets`

**Correctness:** CORRECT

The old design was fundamentally broken: `rebalance()` added idle to `deployedAssets` but never moved tokens out, so `totalAssets = idle + deployed` double-counted everything. The fix properly converts this to a pure simulation vault.

**Blast radius:** Isolated to AlwaysLPVault. No impact on ILAlphaVault or HODLVault.

---

### C-1: Withdraw/Redeem Override with Fee Deduction

**What changed:**
- `withdraw()` and `redeem()` fully override ERC4626 base, implementing:
  - TWAP check
  - `_ensureIdle()` to pull LP if needed
  - Fee calculation and accumulation
  - Manual share burning and token transfer

**Correctness:** MOSTLY CORRECT with edge cases

**Issue 1 -- Zero shares / zero assets:**
- `withdraw(0, ...)`: `previewWithdraw(0)` returns 0 shares. `_burn(owner_, 0)` is a no-op in solmate. `safeTransfer(receiver, 0)` succeeds. This wastes gas but is not exploitable.
- `redeem(0, ...)`: `previewRedeem(0)` returns 0 assets. `require(assets != 0, "ZERO_ASSETS")` catches this. CORRECT.

**Issue 2 -- type(uint256).max:**
- `withdraw(type(uint256).max, ...)`: `_ensureIdle` will try to pull LP, then `previewWithdraw` will compute an enormous share count, `_burn` will revert if owner doesn't have enough shares. SAFE -- reverts naturally.
- `redeem(type(uint256).max, ...)`: `_burn(owner_, type(uint256).max)` will revert on underflow if owner has fewer shares. SAFE.

**Issue 3 -- Fee-on-transfer interaction:**
`withdraw()` computes `fee = (assets * withdrawalFeeBps) / 10_000`, then transfers `assets - fee`. But `assets` is the requested amount. The shares burned are `previewWithdraw(assets)` which is based on the FULL `assets` amount (not `assets - fee`). This means the user pays the fee from their share value but the fee accounting is based on the gross amount. This is consistent and intentional -- the user requests X assets worth, pays shares for X, but receives X minus fee.

**Issue 4 -- No `whenNotPaused` on withdraw/redeem:**
Explicitly intentional -- comment says "users must be able to withdraw after emergency." CORRECT design choice.

**Blast radius:** All user withdrawal paths.

---

### L-6: claimFees Partial Claim

**What changed:**
- v1: `accumulatedFees = 0; asset.safeTransfer(to, fees)` -- would revert if balance < fees
- v2: `claimable = min(fees, available); accumulatedFees = fees - claimable; safeTransfer(to, claimable)`

**Correctness:** CORRECT but leaves residual

**Residual fee analysis:**
If `accumulatedFees > balance`, partial claim leaves `accumulatedFees = fees - claimable > 0`. The residual can be claimed later when more funds are available. This is not a problem -- it's correct accounting. The residual represents fees that have been logically earned but whose underlying tokens are currently deployed in LP.

However, there's a subtle concern: the residual fees inflate `accumulatedFees` while the corresponding assets may be sitting in the LP position. If the LP position suffers IL, the residual fees may never be fully claimable. The owner could claim fees that should belong to depositors. This is mitigated by the fact that fees are only accumulated during withdrawals (when assets are already being returned).

**Blast radius:** Owner-only function, isolated.

---

### M-3: Tick Spacing Alignment (ILAlphaHook.setLPRange)

**What changed:**
- Added `require(tickLower % spacing == 0 && tickUpper % spacing == 0)`

**Correctness:** CORRECT. Without this, `modifyLiquidity` would revert at the PoolManager level with a less descriptive error.

**Blast radius:** Owner-only admin function.

---

### M-4: Lower >= Upper Guard (ILAlphaHook.afterInitialize)

**What changed:**
- Added `if (lower >= upper) upper = lower + spacing;`

**Correctness:** CORRECT. Edge case when tick is near min/max tick and half-range calculation produces `lower >= upper`. The fix ensures a minimum 1-spacing-wide range.

**Blast radius:** Pool initialization only.

---

### Medium/Low: Zero-Address Checks, Reentrancy Guard, SafeTransfer

**transferOwnership, setKeeper, claimFees:** Added `require(addr != address(0))`. CORRECT.

**SwapHelper:** Added `_locked` reentrancy guard and `safeTransferFrom`. CORRECT. The reentrancy guard prevents re-entry through `poolManager.unlock()` callbacks.

**Blast radius:** Minimal, localized fixes.

---

## 2. Regression Analysis

### Regression 1: `_executeRemoveLiquidity` now settles negative deltas

In v1, `_executeRemoveLiquidity` only took positive deltas (receiving tokens back). In v2, it calls `_settleDelta(delta)` which also settles negative deltas. During liquidity removal, negative deltas can occur if the vault owes fees to the pool. This is CORRECT -- v1 was actually buggy here (would silently ignore fee debts). v2 properly handles both directions.

### Regression 2: `_computeLiquidity` reads pool state twice

`_executeAddLiquidity` calls `_computeLiquidity(assets)` which reads `getSlot0` and `getPoolStrategy`. Then `_executeAddLiquidity` calls `getPoolStrategy` again for the `modifyLiquidity` call. This is redundant but not a bug -- both reads happen within the same `unlock` callback, so pool state is consistent.

### Regression 3: No new regressions in BaseVault or HODLVault

These files were not modified in the v2 changes.

---

## 3. Test Coverage Assessment

### What IS tested:

| Fix | Test Coverage |
|-----|--------------|
| H-6 AlwaysLPVault | `test_alwaysLP_totalAssets_noDoubleCount` -- verifies rebalance doesn't inflate totalAssets |
| M-3 Tick alignment | `testFuzz_setLPRange_lowerMustBeLessThanUpper` updated to align ticks to spacing |
| H-4 Rate limiting | `test_keeper_pushVolEstimate` -- verifies capped baseline |
| Withdrawal fee | `test_withdrawalFee_recorded`, `test_claimFees_onlyOwner`, `test_setWithdrawalFee_maxCap` |
| Access control | Multiple tests for onlyOwner, onlyKeeper |
| Emergency flow | `test_emergencyWithdraw_e2e` -- full lifecycle test |

### What is NOT tested (GAPS):

| Fix | Missing Test |
|-----|-------------|
| **H-1 TWAP oracle** | No test for `getTwapTick()` directly. No test for fresh pool fallback. No test for buffer overflow attack (10 swaps in one block). No test for 1-hour expiry. **CRITICAL GAP.** |
| **H-2 Slippage check** | No test for `_checkSlippage()` or `SlippageExceeded` revert. No test for `setMaxSlippageBps()`. **HIGH GAP.** |
| **H-7 Cross-token totalAssets** | No test verifying only one side is counted. Only implicit coverage via existing `totalAssets` tests with 18-decimal 1:1 pair. **MEDIUM GAP.** |
| **C-1 withdraw/redeem override** | No test for `withdraw()` (only `redeem()` is tested). No edge case tests for zero amounts or max uint. No test verifying fee is actually deducted from transfer amount. **HIGH GAP.** |
| **L-6 Partial fee claim** | No test for `claimFees` when `balance < accumulatedFees`. **LOW GAP.** |
| **Remove-side slippage** | Not implemented, not tested. **MEDIUM GAP.** |
| **Zero-address checks** | No tests for `transferOwnership(address(0))` or `setKeeper(address(0))` reverting. **LOW GAP.** |

---

## 4. Summary of Findings

### New Issues Introduced by v2 Fixes

| ID | Severity | Finding |
|----|----------|---------|
| DR-1 | HIGH | TWAP circular buffer can be filled in a single block (no same-block dedup for observations) |
| DR-2 | MEDIUM | Slippage check missing on `_executeRemoveLiquidity()` |
| DR-3 | MEDIUM | TWAP fallback to `lastTick` on fresh/stale pools defeats the fix's purpose |
| DR-4 | LOW | Slippage `expected` parameter is full `assets` but LP only uses ~half, making effective tolerance ~2x stated |
| DR-5 | LOW | `getVaultMetrics.deployedValue` still sums both tokens (`v0 + v1`) while `totalAssets` correctly uses only one -- inconsistent view for off-chain consumers |

### Fixes Verified Correct

| Fix ID | Status |
|--------|--------|
| H-6 AlwaysLPVault | CORRECT, well-tested |
| H-7 Cross-token totalAssets | CORRECT (conservative) |
| M-3 Tick spacing | CORRECT |
| M-4 Lower >= upper | CORRECT |
| L-6 Partial fee claim | CORRECT |
| Zero-address checks | CORRECT |
| SwapHelper reentrancy + safeTransfer | CORRECT |

### Recommended Actions Before Deployment

1. **DR-1 (HIGH):** Add timestamp dedup to `_recordTickObservation()` -- skip if `block.timestamp == last observation timestamp`
2. **DR-2 (MEDIUM):** Add slippage check to `_executeRemoveLiquidity()`
3. **DR-3 (MEDIUM):** Consider reverting in `getTwapTick()` when `totalWeight == 0` instead of silent fallback, or require minimum observation count
4. **Test gaps:** Add targeted tests for TWAP oracle, slippage revert, withdraw() edge cases, and cross-token totalAssets
5. **DR-5 (LOW):** Align `getVaultMetrics.deployedValue` with `totalAssets` single-token logic
