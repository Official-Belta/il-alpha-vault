# 04 - Entry Point Analysis (v2)

Re-enumeration of all state-changing entry points after v2 fixes (C-1, C-2, C-3, C-4, H-1, H-2, H-4, H-5, H-6, H-7, L-6, M-3, M-4).

**Scope:** 6 contracts in `contracts/src/`

**Access Level Key:**
- **PUBLIC** -- callable by anyone, no access control
- **KEEPER** -- restricted to `keeper` address or `owner`
- **OWNER** -- restricted to `owner` address only
- **POOL_MANAGER** -- restricted to Uniswap V4 PoolManager contract only
- **PENDING_OWNER** -- restricted to `pendingOwner` address only

---

## 1. ILAlphaHook.sol

| # | Function | Access | State Changes | External Calls | Value Flow | Risk |
|---|----------|--------|---------------|----------------|------------|------|
| 1 | `afterInitialize()` | POOL_MANAGER | `poolStates[poolId]`, `volOracles[poolId]` | None | None | LOW |
| 2 | `afterSwap()` | POOL_MANAGER | `volOracles[poolId].*`, `poolStates[poolId].*`, `tickObservations[poolId][]`, `observationIndex[poolId]` | `poolManager.getSlot0()` | None | MEDIUM |
| 3 | `pushVolEstimate()` | KEEPER | `volOracles[poolId].ewmaVar`, `.lastTimestamp` | None | None | MEDIUM (was HIGH) |
| 4 | `triggerEvaluation()` | KEEPER | `poolStates[poolId].isLPActive`, `.lastToggleTime` | None | None | MEDIUM |
| 5 | `setLPRange()` | OWNER | `poolStates[poolId].tickLower`, `.tickUpper` | None | None | MEDIUM |
| 6 | `transferOwnership()` | OWNER | `pendingOwner` | None | None | LOW |
| 7 | `acceptOwnership()` | PENDING_OWNER | `owner`, `pendingOwner` | None | None | LOW |
| 8 | `setKeeper()` | OWNER | `keeper` | None | None | LOW |
| 9 | `setLambda()` | OWNER | `volOracles[poolId].lambda` | None | None | MEDIUM |

**New internal function (not an entry point):** `_recordTickObservation()` -- writes to `tickObservations` circular buffer on every `afterSwap`. View function `getTwapTick()` added (not state-changing, excluded).

---

## 2. ILAlphaVault.sol

| # | Function | Access | Modifiers | State Changes | External Calls | Value Flow | Risk |
|---|----------|--------|-----------|---------------|----------------|------------|------|
| 1 | `deposit()` | PUBLIC | `whenNotPaused`, `nonReentrant` | `totalSupply`, `balanceOf[receiver]`, `_locked` | `asset.safeTransferFrom()`, `_checkTWAP()` | Tokens IN | MEDIUM |
| 2 | **`mint()` [NEW override]** | PUBLIC | `whenNotPaused`, `nonReentrant` | `totalSupply`, `balanceOf[receiver]`, `_locked` | `asset.safeTransferFrom()`, `_checkTWAP()` | Tokens IN | MEDIUM (was CRITICAL) |
| 3 | **`withdraw()` [NEW override]** | PUBLIC | `nonReentrant` | `totalSupply`, `balanceOf`, `allowance`, `accumulatedFees`, `deployedLiquidity`, `_locked`, `_pendingAction` | `asset.safeTransfer()`, `poolManager.unlock()`, `_checkTWAP()` | Tokens OUT (fee deducted) | MEDIUM-HIGH (was CRITICAL) |
| 4 | **`redeem()` [NEW override]** | PUBLIC | `nonReentrant` | Same as `withdraw()` | Same as `withdraw()` | Tokens OUT (fee deducted) | MEDIUM-HIGH (was CRITICAL) |
| 5 | `rebalance()` | PUBLIC | `whenNotPaused`, `nonReentrant` | `deployedLiquidity`, `_locked`, `_pendingAction` | `hook.isLPActive()`, `poolManager.unlock()`, `poolManager.modifyLiquidity()` | Tokens between vault and PoolManager | MEDIUM-HIGH (was HIGH) |
| 6 | `unlockCallback()` | POOL_MANAGER | -- | `deployedLiquidity` | `poolManager.modifyLiquidity()`, `poolManager.sync()`, `poolManager.settle()`, `poolManager.take()` | Tokens between vault and PoolManager | MEDIUM |
| 7 | `transferOwnership()` | OWNER | -- | `pendingOwner` | None | None | LOW |
| 8 | `acceptOwnership()` | PENDING_OWNER | -- | `owner`, `pendingOwner` | None | None | LOW |
| 9 | `setPoolKey()` | OWNER | -- | `poolKey` | None | None | MEDIUM |
| 10 | `setPaused()` | OWNER | -- | `paused` | None | None | LOW |
| 11 | `setKeeper()` | OWNER | -- | `keeper` | None | None | LOW |
| 12 | `setDepositCap()` | OWNER | -- | `depositCap` | None | None | LOW |
| 13 | `setTwapThreshold()` | OWNER | -- | `twapThreshold` | None | None | LOW (was MEDIUM) |
| 14 | `setWithdrawalFeeBps()` | OWNER | -- | `withdrawalFeeBps` | None | None | LOW |
| 15 | **`setMaxSlippageBps()` [NEW]** | OWNER | -- | `maxSlippageBps` | None | None | LOW |
| 16 | `claimFees()` | OWNER | -- | `accumulatedFees` | `asset.safeTransfer()` | Tokens OUT | MEDIUM |
| 17 | `emergencyWithdraw()` | OWNER | `nonReentrant` | `deployedLiquidity`, `paused`, `_locked`, `_pendingAction` | `poolManager.unlock()` | Tokens IN (LP removed) | MEDIUM |

### Inherited ERC20 (from solmate)

| Function | Access | Risk |
|----------|--------|------|
| `transfer()` | PUBLIC | LOW |
| `transferFrom()` | PUBLIC | LOW |
| `approve()` | PUBLIC | LOW |
| `permit()` | PUBLIC | LOW |

---

## 3. BaseVault.sol

Abstract. No additional state-changing entry points. View-only overrides (`convertToShares`, `convertToAssets`, `previewDeposit`, `previewMint`, `previewWithdraw`, `previewRedeem`).

---

## 4. SwapHelper.sol

| # | Function | Access | State Changes | External Calls | Value Flow | Risk |
|---|----------|--------|---------------|----------------|------------|------|
| 1 | `swap()` | OWNER | `_pendingKey`, `_pendingZeroForOne`, `_pendingAmount`, `_isSwap`, `_locked` | `poolManager.unlock()` | Tokens: caller <-> PoolManager | MEDIUM |
| 2 | `addLiquidity()` | OWNER | `_pendingKey`, `_pendingAmount`, `_isSwap`, `_locked` | `poolManager.unlock()` | Tokens: caller <-> PoolManager | LOW |
| 3 | `unlockCallback()` | POOL_MANAGER | None | `poolManager.swap()` or `poolManager.modifyLiquidity()`, `ERC20.transferFrom()` | Tokens: caller <-> PoolManager | MEDIUM |

---

## 5. AlwaysLPVault.sol

| # | Function | Access | Risk |
|---|----------|--------|------|
| 1 | `deposit()` (inherited) | PUBLIC | LOW |
| 2 | `mint()` (inherited) | PUBLIC | LOW |
| 3 | `withdraw()` (inherited) | PUBLIC | LOW |
| 4 | `redeem()` (inherited) | PUBLIC | LOW |
| 5 | `rebalance()` | PUBLIC | LOW |
| 6-9 | `transfer/transferFrom/approve/permit` | PUBLIC | LOW |

**H-6 FIX verified:** `deployedAssets` phantom accounting removed. `totalAssets()` = `asset.balanceOf(address(this))` only. `rebalance()` is now a no-op that just emits an event.

---

## 6. HODLVault.sol

| # | Function | Access | Risk |
|---|----------|--------|------|
| 1-4 | `deposit/mint/withdraw/redeem` (inherited) | PUBLIC | LOW |
| 5-8 | `transfer/transferFrom/approve/permit` | PUBLIC | LOW |

No changes from v1. Purely holds assets.

---

## Verification of Previous Top-5 Risk Mitigations

### 1. `mint()` -- was CRITICAL, now MEDIUM

**Status: MITIGATED (C-2 FIX)**

The `mint()` function is now fully overridden in `ILAlphaVault.sol` (lines 184-196) with:
- `whenNotPaused` modifier
- `nonReentrant` modifier
- `previewMint()` -> minimum deposit check (`assets < VIRTUAL_ASSETS`)
- `depositCap` enforcement
- `_checkTWAP()` price manipulation check

**Residual risk:** The override calls `super.mint()` which re-enters solmate's `mint()`. This is safe because solmate's `mint()` calls `previewMint()` and `afterDeposit()` which are both read-only / empty. The `nonReentrant` guard covers the entire flow.

### 2. `withdraw()` / `redeem()` -- were CRITICAL, now MEDIUM-HIGH

**Status: MITIGATED (C-1 + H-5 FIX)**

Both functions are now fully overridden (lines 329-370) with:
- `nonReentrant` modifier (H-5 fix)
- `_checkTWAP()` price manipulation check
- `_ensureIdle()` -- pulls LP if needed
- **Fee is actually deducted:** `asset.safeTransfer(receiver, assets - fee)` (C-1 fix)
- Allowance checks are done manually in the override
- `beforeWithdraw()` is now an intentional no-op

**Residual risk:** `withdraw()` and `redeem()` intentionally lack `whenNotPaused` (design choice: users must always be able to exit). This is correct behavior.

**Note:** No `whenNotPaused` also means deposits via `mint()`/`deposit()` are blocked when paused, but withdrawals remain open. This is the expected emergency behavior.

### 3. `rebalance()` -- was HIGH, now MEDIUM-HIGH

**Status: MITIGATED (H-2 FIX)**

Slippage check added via `_checkSlippage()` (line 274) inside `_executeAddLiquidity()`:
- Compares actual token cost against `expected + (expected * maxSlippageBps) / 10_000`
- `maxSlippageBps` defaults to 100 (1%), capped at 500 (5%) by `setMaxSlippageBps()`

**Residual risk:**
- Slippage check is only on `_executeAddLiquidity()`, NOT on `_executeRemoveLiquidity()` (lines 312-323). LP removal has no minimum output check.
- `rebalance()` is still publicly callable -- anyone can trigger it, but sandwich attacks are now bounded by the slippage parameter.

### 4. `pushVolEstimate()` -- was HIGH, now MEDIUM

**Status: MITIGATED (H-4 FIX)**

Rate limit tightened (line 385):
- Cap changed from 4x to 2x current value: `maxExternal = currentVar * 2`
- Zero baseline capped to `1e18` (not `type(uint128).max`): prevents unbounded first push

**Residual risk:** Repeated calls can still ratchet the oracle upward. Each call blends 50/50, so after push: `newVar = (current + 2*current)/2 = 1.5*current`. Repeated calls: 1x -> 1.5x -> 2.25x -> 3.375x -> ... This is exponential growth per call. A keeper key compromise still allows significant oracle drift, just more slowly. Per-block or per-hour rate limiting would further mitigate.

### 5. `afterSwap()` -- was MEDIUM-HIGH, now MEDIUM

**Status: MITIGATED (H-1 FIX)**

Tick observations are now recorded via `_recordTickObservation()` (line 265):
- Circular buffer of 10 observations (`TWAP_WINDOW`)
- `getTwapTick()` computes time-weighted average from observations within 1 hour
- `_checkTWAP()` in the vault uses real TWAP (not just `lastTick`)
- Observations weighted by recency (newer = higher weight)

**Residual risk:** The TWAP window is small (10 observations). In a low-activity pool, an attacker could fill all 10 slots with manipulated ticks across 10 swaps, effectively controlling the TWAP. This is harder than manipulating a single `lastTick` but still feasible for a well-funded attacker in thin pools.

---

## Updated Top 5 Highest-Risk Entry Points (v2)

### 1. `ILAlphaVault.withdraw()` / `redeem()` -- MEDIUM-HIGH

**File:** `contracts/src/ILAlphaVault.sol`, lines 329-370

Still the highest-risk entry points due to the combination of:
- **LP removal path:** `_ensureIdle()` may trigger `_removeLiquidity()` which has no slippage check. An attacker can sandwich a withdrawal that forces LP removal to extract value.
- **Fee-on-transfer interaction:** The fee is deducted from the transferred amount, but `previewWithdraw(assets)` computes shares based on the full `assets` amount. This means the user burns shares worth `assets` but only receives `assets - fee`. This is a feature, not a bug, but the ERC-4626 specification expects `withdraw(assets)` to deliver exactly `assets` to the receiver. Non-conformant behavior may confuse integrators.
- **`accumulatedFees` drains idle balance:** Fees accumulate as a claim against idle assets. If fees are not claimed regularly, they reduce the effective `totalAssets()` for depositors (since `totalAssets()` includes fees sitting in idle balance). The L-6 fix in `claimFees()` handles the case where `accumulatedFees > available`, but the accounting is still fragile.

### 2. `ILAlphaVault.rebalance()` -- MEDIUM-HIGH

**File:** `contracts/src/ILAlphaVault.sol`, line 209

Mitigated with slippage check on add, but:
- **No slippage check on LP removal:** `_executeRemoveLiquidity()` (line 312) accepts whatever the pool returns. A sandwich attacker can manipulate the price before triggering `rebalance()` when LP is being removed.
- **Still publicly callable:** Anyone can call it. The result is deterministic (based on `hook.isLPActive()`), but the timing is attacker-controlled.
- **50/50 split assumption:** `_computeLiquidity()` uses `assets/2, assets/2` which leaks value when the pool price is off-center relative to the tick range.

### 3. `ILAlphaHook.pushVolEstimate()` -- MEDIUM

**File:** `contracts/src/ILAlphaHook.sol`, line 377

2x rate limit is better than 4x, but:
- **Exponential ratcheting still possible:** Each call can move the oracle by 1.5x (blend of current + 2x current). Five calls: 1x -> 1.5x -> 2.25x -> 3.375x -> 5.06x -> 7.59x. No per-block or time-based rate limiting.
- **No downward rate limit:** A keeper can also suppress vol by pushing `externalVar = 0`, blending to `currentVar/2` per call. Five calls: 1x -> 0.5x -> 0.25x -> 0.125x -> 0.0625x -> 0.03125x. This could force LP activation into high-vol conditions.
- **Keeper key is a single point of trust:** Keeper and owner share the `onlyKeeper` modifier. A compromised owner key gives full oracle control.

### 4. `ILAlphaHook.afterSwap()` -- MEDIUM

**File:** `contracts/src/ILAlphaHook.sol`, line 235

- **TWAP window is small:** 10 observations. An attacker executing 10 swaps across different blocks can fill the entire buffer with manipulated ticks.
- **Volume spike cooldown bypass is still present:** Large swaps (>3x EWMA) force LP off, bypassing 24h cooldown. This is by design (emergency protection) but an attacker with sufficient capital can toggle LP off at will.
- **Same-block swaps skip vol oracle:** `elapsed == 0` check in `_updateVolOracle()` means MEV bots can execute swaps without affecting the EWMA variance (they do still affect volume EWMA though).

### 5. `ILAlphaVault.emergencyWithdraw()` -- MEDIUM

**File:** `contracts/src/ILAlphaVault.sol`, line 536

- **No slippage check on emergency LP removal:** Uses the same `_removeLiquidity()` which has no minimum output. An attacker monitoring the mempool can sandwich the emergency withdrawal.
- **Pauses the vault:** After emergency, only `withdraw()`/`redeem()` work (no `whenNotPaused` on those). Owner must call `setPaused(false)` to re-enable deposits. This is correct but worth noting.
- **Owner-only:** Mitigated by access control, but a compromised owner key can force-extract LP at a bad price.

---

## New Attack Vectors Introduced by v2 Fixes

### A. ERC-4626 Non-Conformance in `withdraw()` (C-1 Fix Side Effect)

The `withdraw()` override burns shares worth `assets` but transfers `assets - fee` to the receiver. Per ERC-4626, `withdraw(assets, receiver, owner)` should deliver exactly `assets` to the receiver. This breaks composability with protocols that rely on ERC-4626 conformance (e.g., yield aggregators, lending protocols using vault shares as collateral).

**Impact:** Integrator loss. A protocol calling `vault.withdraw(1000e6, ...)` expecting to receive exactly 1000 USDC will receive 999e6 USDC (with 0.1% fee). Over many interactions, this silently drains integrator funds.

**Recommendation:** Either burn more shares to cover the fee (so receiver gets exactly `assets`), or document the non-conformance prominently and override `maxWithdraw()` / `previewWithdraw()` to account for fees.

### B. `accumulatedFees` Phantom Balance (C-1 + L-6 Interaction)

The fee is deducted from what the user receives, so the fee tokens remain in the vault's idle balance. But `totalAssets()` counts the full idle balance including fee tokens. This means:
- `totalAssets()` is inflated by `accumulatedFees`
- New depositors get fewer shares than they should (share price is artificially high)
- When owner claims fees via `claimFees()`, `totalAssets()` drops, diluting existing depositors

**Impact:** Wealth transfer from late depositors to early depositors and the fee collector. The magnitude is proportional to unclaimed fees / totalAssets.

**Recommendation:** Subtract `accumulatedFees` from `totalAssets()`, i.e., `return idle - accumulatedFees + lpValue`.

### C. Asymmetric Slippage Protection (H-2 Fix Incompleteness)

Slippage check exists on `_executeAddLiquidity()` but not on `_executeRemoveLiquidity()`. This creates an asymmetry:
- Adding LP: protected (bounded by `maxSlippageBps`)
- Removing LP: unprotected (accepts any price)

An attacker can exploit this by:
1. Manipulating pool price
2. Triggering `rebalance()` when hook signals LP-off (removal path)
3. LP is removed at manipulated price with no protection
4. Attacker reverses manipulation, profiting from the slippage

The same applies to `_ensureIdle()` calls from `withdraw()`/`redeem()`.

**Recommendation:** Add a slippage check to `_executeRemoveLiquidity()` comparing returned assets against the expected value from `_getDeployedLPValue()`.

### D. TWAP Oracle Bootstrapping Window (H-1 Fix Side Effect)

When a pool is first initialized or has low activity, the TWAP buffer may have fewer than 10 observations. `getTwapTick()` handles this gracefully (skips zero-timestamp entries, falls back to `lastTick`). However, during the bootstrapping period:
- The TWAP is based on very few observations (possibly just 1-2)
- An attacker can fill the buffer with manipulated ticks early in the pool's life
- `_checkTWAP()` uses this weak TWAP as the reference, providing a false sense of security

This is primarily relevant during the first hour of a pool's existence.

**Recommendation:** Consider a minimum observation count before trusting the TWAP (e.g., require at least 5 observations spanning at least 10 minutes).

### E. `setMaxSlippageBps()` Missing Event Emission

The new `setMaxSlippageBps()` function (line 513) does not emit an event when the slippage parameter is changed. This makes off-chain monitoring blind to slippage parameter changes. An owner could set `maxSlippageBps = 500` (5%) silently, weakening sandwich protection.

**Recommendation:** Add an event `MaxSlippageUpdated(uint256 oldBps, uint256 newBps)`.

---

## Summary Statistics (v2)

| Contract | Total State-Changing Entry Points | PUBLIC | KEEPER | OWNER | POOL_MANAGER | PENDING_OWNER |
|----------|----------------------------------|--------|--------|-------|--------------|---------------|
| ILAlphaHook | 9 | 0 | 2 | 4 | 2 | 1 |
| ILAlphaVault | 21 (incl. inherited ERC20) | 8 | 0 | 9 | 1 | 1 |
| BaseVault | 0 (abstract) | -- | -- | -- | -- | -- |
| SwapHelper | 3 | 0 | 0 | 2 | 1 | 0 |
| AlwaysLPVault | 10 (incl. inherited) | 9 | 0 | 0 | 0 | 0 |
| HODLVault | 8 (incl. inherited) | 8 | 0 | 0 | 0 | 0 |

**Total unique state-changing entry points: 51** (was 46; +5 from new overrides and `setMaxSlippageBps`)

### New Entry Points in v2

| Function | Contract | Type |
|----------|----------|------|
| `mint()` override | ILAlphaVault | C-2 fix -- guards parity with `deposit()` |
| `withdraw()` override | ILAlphaVault | C-1 + H-5 fix -- fee deduction + reentrancy |
| `redeem()` override | ILAlphaVault | C-1 + H-5 fix -- fee deduction + reentrancy |
| `setMaxSlippageBps()` | ILAlphaVault | H-2 related -- configurable slippage bound |
| `_recordTickObservation()` (internal) | ILAlphaHook | H-1 fix -- TWAP data recording |

### Mitigation Status Summary

| v1 Finding | v1 Severity | v2 Status | v2 Severity | Fix Reference |
|------------|-------------|-----------|-------------|---------------|
| `mint()` bypass | CRITICAL | FIXED | MEDIUM | C-2 |
| `withdraw()`/`redeem()` fee not deducted | CRITICAL | FIXED (with caveats) | MEDIUM-HIGH | C-1, H-5 |
| `rebalance()` no slippage | HIGH | PARTIALLY FIXED | MEDIUM-HIGH | H-2 (add only) |
| `pushVolEstimate()` 4x rate limit | HIGH | FIXED (2x limit) | MEDIUM | H-4 |
| `afterSwap()` no TWAP | MEDIUM-HIGH | FIXED | MEDIUM | H-1 |

### Remaining Action Items

1. **Add slippage check to `_executeRemoveLiquidity()`** -- the asymmetric protection is exploitable.
2. **Subtract `accumulatedFees` from `totalAssets()`** -- prevents share price inflation from unclaimed fees.
3. **Add per-hour rate limiting to `pushVolEstimate()`** -- exponential ratcheting is still possible.
4. **Add minimum TWAP observation count** -- bootstrapping period is vulnerable.
5. **Emit event from `setMaxSlippageBps()`** -- parity with other admin setters.
6. **Document ERC-4626 non-conformance** in `withdraw()` -- integrators need to know fees are deducted from the output.
