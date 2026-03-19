# Trail of Bits "Building Secure Contracts" Assessment -- v2

**Project:** IL Alpha Vault
**Date:** 2026-03-20
**Methodology:** Trail of Bits SCV framework + Building Secure Contracts guidelines
**Scope:** `ILAlphaHook.sol`, `ILAlphaVault.sol`, `BaseVault.sol`, `SwapHelper.sol`, `AlwaysLPVault.sol`, `HODLVault.sol`
**Tests reviewed:** `ILAlphaHook.t.sol`, `ILAlphaVault.t.sol`, `ControlVaults.t.sol`
**Context:** v2 re-assessment after security fixes applied to address v1 findings

---

## Part A: Updated Code Maturity Scorecard

| # | Category | v1 | v2 | Delta | Notes |
|---|----------|:--:|:--:|:-----:|-------|
| 1 | **Arithmetic** | 4/5 | 4/5 | -- | Unchanged. EWMA calculations still use explicit uint128 capping. `FixedPointMathLib.mulDivDown/Up` for share math. Minor precision loss in `squaredReturn * 3600 / elapsed` for large elapsed values remains. |
| 2 | **Auditing & Logging** | 4/5 | 5/5 | +1 | **Fixed.** Events now emitted on all admin state changes: `KeeperUpdated`, `DepositCapUpdated`, `TwapThresholdUpdated`, `WithdrawalFeeUpdated`, `PoolKeyUpdated`, `PauseUpdated`, `OwnershipTransferStarted`, `OwnershipTransferred`. This was v1 finding M-3/H-8. |
| 3 | **Authentication & Access Control** | 4/5 | 4/5 | -- | Two-step ownership on both Hook and Vault. Zero-address checks added on `setKeeper`, `transferOwnership`, `claimFees`. Still no timelock or multi-sig enforcement (acceptable for current stage). |
| 4 | **Complexity Management** | 4/5 | 4/5 | -- | Unchanged. Clean separation maintained. `_pendingAction` enum pattern still clear. Withdraw/redeem overrides add some complexity but are well-structured. |
| 5 | **Decentralization** | 3/5 | 3/5 | -- | Owner still has broad powers without timelock. `rebalance()` remains public (good). Keeper vol push rate-limited to 2x now (improved from 4x). Still single-EOA owner risk. |
| 6 | **Documentation** | 3/5 | 3/5 | -- | NatSpec improved slightly with fix annotations (e.g., `/// @notice C-1 FIX`, `/// @notice H-7 FIX`). Still no formal specification or standalone architecture docs. |
| 7 | **MEV & Frontrunning** | 3/5 | 4/5 | +1 | **Improved.** H-1 fixed: real TWAP tick accumulator with circular buffer of 10 observations, time-weighted by recency, ignoring observations older than 1 hour. H-2 fixed: slippage check via `_checkSlippage()` on LP add operations with configurable `maxSlippageBps` (default 1%, max 5%). Withdrawal fee deters sandwich attacks. Volume spike detection remains. Remaining concern: `_executeRemoveLiquidity` does not have explicit slippage protection (though removal is less sandwichable than addition). |
| 8 | **Low-level Code** | 5/5 | 5/5 | -- | Unchanged. No assembly, no delegatecall, no selfdestruct. All typed interfaces. |
| 9 | **Testing** | 4/5 | 4/5 | -- | Test count still ~50+. New tests added for: `setPoolKey` currency validation, deposit cap enforcement, withdrawal fee recording, `mint()` coverage is implicit but no explicit `mint()` test. Still missing: invariant tests, formal verification, cross-contract reentrancy tests. |

**Aggregate Score: 36/45 (80%)** -- up from 34/45 (76%) in v1

---

## Part B: Updated Vulnerability Scan (SCV Framework)

### v1 Findings Remediation Status

| v1 ID | Severity | Finding | Status | Notes |
|-------|----------|---------|--------|-------|
| C-1 | CRITICAL | Withdrawal fee never deducted from user transfer | **FIXED** | `withdraw()` and `redeem()` fully overridden. Fee deducted from transfer: `asset.safeTransfer(receiver, assets - fee)`. `beforeWithdraw()` is now intentionally empty. |
| C-2 | CRITICAL | `mint()` bypasses all deposit guards | **FIXED** | `mint()` overridden with `whenNotPaused`, `nonReentrant`, `DepositTooSmall`, `DepositCapExceeded`, and `_checkTWAP()` guards. |
| C-3 | CRITICAL | `setPoolKey()` callable with active liquidity | **FIXED** | Guard added: `if (deployedLiquidity > 0) revert LPStillDeployed()`. |
| C-4 | CRITICAL | `setTwapThreshold()` has no bounds validation | **FIXED** | Bounds enforced: `if (_threshold < 10 \|\| _threshold > 2000) revert TwapThresholdOutOfRange()`. |
| H-1 | HIGH | TWAP check uses single stale tick, not true TWAP | **FIXED** | Circular buffer of 10 tick observations (`TickObservation` struct) recorded per swap. `getTwapTick()` computes time-weighted average with recency weighting, ignoring observations older than 1 hour. |
| H-2 | HIGH | No slippage protection on LP add/remove | **PARTIALLY FIXED** | `_checkSlippage()` added for `_executeAddLiquidity()`. Configurable `maxSlippageBps` with owner setter (max 5%). `_executeRemoveLiquidity()` still lacks explicit slippage check. |
| H-3 | HIGH | 50/50 asset split assumes vault holds both tokens | **ACKNOWLEDGED** | Comment updated: `/// @dev H-3 NOTE: 50/50 split assumes vault holds both tokens. Phase 4: pre-swap.` Deferred to Phase 4 implementation. Risk remains but is documented. |
| H-4 | HIGH | Keeper `pushVolEstimate` rate limit 4x, not 2x | **FIXED** | Rate limit changed to 2x. Zero-baseline capped to `1e18` instead of `type(uint128).max`. |
| H-5 | HIGH | `withdraw()`/`redeem()` missing reentrancy guard | **FIXED** | Both `withdraw()` and `redeem()` now have `nonReentrant` modifier. |
| H-6 | HIGH | AlwaysLPVault double-counts assets | **FIXED** | `AlwaysLPVault.totalAssets()` now returns `asset.balanceOf(address(this))` only. No `deployedAssets` tracking. |
| H-7 | HIGH | `totalAssets()` sums two token amounts without price conversion | **FIXED** | `totalAssets()` now only counts LP value in the vault's asset token. Conservative approach: understates totalAssets when LP holds the counterpart token. |
| H-8 | HIGH | Admin parameter changes emit no events | **FIXED** | Events added to all admin setters. See category 2 above. |
| M-1 | MEDIUM | Keeper can manipulate vol oracle from zero to max | **FIXED** | Zero-baseline capped to `1e18`, rate limit reduced to 2x. First push from zero yields `(0 + 1e18) / 2 = 5e17` max. |
| M-3 | MEDIUM | `setLPRange` missing tick spacing validation | **FIXED** | Alignment check added: `require(tickLower % spacing == 0 && tickUpper % spacing == 0)`. |
| M-4 | MEDIUM | No zero-address checks | **FIXED** | Zero-address checks added on `setKeeper()`, `transferOwnership()`, `claimFees()`. |
| L-5 | MEDIUM | `setPoolKey` can be called with active LP | **FIXED** | See C-3 above. |
| L-6 | LOW | `claimFees` could exceed available balance | **FIXED** | `claimFees()` now checks `asset.balanceOf(address(this))` and only transfers the minimum of `accumulatedFees` and available balance. |

### New / Remaining Findings

#### HIGH Severity -- None New

#### MEDIUM Severity

##### M-1 (Remaining): `_executeRemoveLiquidity` Lacks Slippage Protection

**Location:** `ILAlphaVault.sol:312-323`
**Description:** While `_executeAddLiquidity` now has `_checkSlippage()`, the removal path does not verify that the amounts received are within acceptable bounds. A MEV bot could sandwich a `rebalance()` removal or an `_ensureIdle()` triggered by withdrawal.
**Impact:** Value extraction during LP removal, though typically less profitable for attackers than add-side manipulation since the vault receives tokens rather than paying them.
**Recommendation:** Add a minimum-amounts check after `_executeRemoveLiquidity` based on expected values from `_getDeployedLPValue()`.

##### M-2 (Remaining): 50/50 Asset Split Still in Effect

**Location:** `ILAlphaVault.sol:281-292`
**Description:** `_computeLiquidity` passes `assets / 2, assets / 2` to `getLiquidityForAmounts`. The vault holds a single asset token, so half the allocation targets a token the vault may not have. This will either revert (if vault lacks token1) or deploy suboptimal liquidity.
**Impact:** Vault may fail to deploy LP or deploys at reduced efficiency. Tests work around this by manually transferring both tokens to the vault.
**Recommendation:** Implement single-sided deposit with pre-swap, or compute correct ratio from current sqrtPrice.

##### M-3 (Remaining): No Timelock on Critical Parameter Changes

**Location:** Multiple admin setters in `ILAlphaVault.sol`
**Description:** Owner can instantly change withdrawal fee (up to 1%), TWAP threshold, deposit cap, max slippage, and pause state. A compromised owner key allows immediate parameter manipulation.
**Impact:** Compromised owner can set withdrawal fee to 1%, disable TWAP protection (set to 2000), or pause deposits while draining fees.
**Recommendation:** Add a timelock (e.g., 48h delay) for sensitive parameter changes. At minimum, consider for `withdrawalFeeBps` and `twapThreshold`.

##### M-4 (Remaining): `LiquidityAmounts` Imported from Test Utils

**Location:** `ILAlphaVault.sol:17`
**Description:** `import {LiquidityAmounts} from "v4-core/test/utils/LiquidityAmounts.sol"` imports from test utility path. This library may not have the same audit/review standard as core contracts.
**Impact:** Potential bugs in liquidity calculation. The library is widely used but its test-utils placement suggests it is not considered production-ready by Uniswap.
**Recommendation:** Vendor the library or use a known-good copy from a production-audited source.

##### M-5 (New): Withdrawal Fee Applied to Full Amount, User Receives Less Than Expected

**Location:** `ILAlphaVault.sol:329-347, 351-370`
**Description:** In `withdraw()`, the user requests `assets` but receives `assets - fee`. The `shares` burned are based on `previewWithdraw(assets)` -- meaning the user pays shares for the full `assets` amount but only receives `assets - fee`. This is a valid fee mechanism, but the ERC-4626 spec expects `withdraw(assets)` to deliver exactly `assets` to the receiver. Similarly, `redeem()` computes assets via `previewRedeem(shares)` but transfers `assets - fee`, so `previewRedeem` is inaccurate.
**Impact:** ERC-4626 spec non-compliance. Integrators calling `previewWithdraw` or `previewRedeem` will get incorrect values. Off-chain accounting will be wrong.
**Recommendation:** Either (a) burn extra shares to cover the fee so the user receives the full `assets`, or (b) override `previewWithdraw`/`previewRedeem` to account for the fee.

#### LOW Severity

##### L-1 (Remaining): `SwapHelper` Uses `safeTransferFrom` from Caller Address

**Location:** `SwapHelper.sol:92, 99, 127, 134`
**Description:** `SwapHelper` is a testnet utility. It now correctly uses `safeTransferFrom` via SafeTransferLib. However, it stores caller address via `abi.encode(msg.sender)` in the unlock callback data, which is safe but unconventional.
**Impact:** Low -- testnet utility only.

##### L-2 (New): TWAP Observation Window May Be Insufficient

**Location:** `ILAlphaHook.sol:97, 113-115, 448-481`
**Description:** The TWAP uses a fixed circular buffer of 10 observations with a 1-hour recency window. In low-activity pools, there may be fewer than 10 observations, reducing TWAP robustness. The fallback to `lastTick` when `totalWeight == 0` reverts to the single-sample behavior that v1 flagged.
**Impact:** In low-activity pools, the TWAP protection degrades to single-sample behavior.
**Recommendation:** Consider a longer observation window or minimum observation count before relying on TWAP. Add a `minObservations` parameter.

##### L-3 (New): `setLPRange` Does Not Emit Event

**Location:** `ILAlphaHook.sol:409-417`
**Description:** While most admin setters in `ILAlphaVault` now emit events, `setLPRange` in `ILAlphaHook` still does not emit an event.
**Impact:** LP range changes are not observable off-chain.
**Recommendation:** Add an event emission.

##### L-4 (New): `withdraw()` Accounting -- `accumulatedFees` May Exceed Actual Holdings

**Location:** `ILAlphaVault.sol:335-336, 364-365`
**Description:** `accumulatedFees` is incremented on every withdrawal, but fees are not actually segregated from vault assets. The fee amount stays in the vault balance and is also counted in `totalAssets()`. When owner calls `claimFees()`, it reduces the vault's actual balance, which will deflate share prices for remaining depositors.
**Impact:** Fee claiming effectively socializes the cost across remaining depositors by reducing `totalAssets()`. The `claimFees` function does cap at available balance (L-6 fix from v1), preventing reverts but not the share price impact.
**Recommendation:** Exclude `accumulatedFees` from `totalAssets()` calculation, or track fees in a separate accounting layer.

##### L-5 (New): `_checkTWAP` Skipped When `deployedLiquidity == 0`

**Location:** `ILAlphaVault.sol:414-416`
**Description:** `_checkTWAP` returns immediately when `deployedLiquidity == 0`. This means deposits have no TWAP protection when the vault is idle (no LP deployed). While the vault has no LP exposure at this point, a depositor could be front-run on the deposit itself if a rebalance occurs in the same block.
**Impact:** Low. The deposit itself is not price-sensitive when no LP is deployed, but a rapid deposit-rebalance sequence could be exploited.

### INFORMATIONAL

| ID | Finding | Location |
|----|---------|----------|
| I-1 | `UNAUDITED` constant remains -- responsible transparency measure | Both contracts |
| I-2 | `annualizedVol` calculation (`hourlyVar * 8760`) is still a rough approximation | ILAlphaHook.sol:424 |
| I-3 | `getVaultMetrics().deployedValue` sums both token amounts (`v0 + v1`) while `totalAssets()` counts only asset token -- inconsistency in view functions | ILAlphaVault.sol:452 |
| I-4 | `beforeWithdraw` is now a no-op but still exists as an override -- could be removed for clarity | ILAlphaVault.sol:388-390 |
| I-5 | Fix annotations in NatSpec (e.g., `C-1 FIX`, `H-7 FIX`) are helpful for review but should be cleaned before production | Multiple |
| I-6 | `setMaxSlippageBps` uses string revert `"Max 5%"` instead of custom error | ILAlphaVault.sol:514 |

---

### SCV Classes Scan (36 Vulnerability Classes)

| # | Vulnerability Class | Status | Notes |
|---|---------------------|--------|-------|
| 1 | Reentrancy (classic) | **Mitigated** | `nonReentrant` on deposit, mint, withdraw, redeem, rebalance, emergencyWithdraw |
| 2 | Reentrancy (cross-function) | **Mitigated** | `_locked` flag covers all external entry points |
| 3 | Reentrancy (read-only) | **Low risk** | `totalAssets()` reads pool state; called within guarded functions |
| 4 | Integer overflow/underflow | **Mitigated** | Solidity 0.8.26 + uint128 capping |
| 5 | Division by zero | **Mitigated** | `elapsed == 0` check in vol oracle; `tickRange > 0` check in IL calc |
| 6 | Precision loss | **Low risk** | `squaredReturn * 3600 / elapsed` for large elapsed; `poolFee * ewmaVolume / 1_000_000` for small products |
| 7 | Unchecked return values | **Mitigated** | SafeTransferLib used in vault and SwapHelper |
| 8 | Oracle manipulation | **Improved** | TWAP accumulator with 10-sample window (was single-sample). Still degraded in low-activity pools |
| 9 | Flash loan attacks | **Improved** | TWAP check + slippage protection + withdrawal fee. Residual risk in low-activity pools |
| 10 | Front-running / MEV | **Improved** | Slippage check on LP add. Still no slippage on LP remove |
| 11 | Sandwich attacks | **Improved** | TWAP + slippage + withdrawal fee deter sandwich. Not fully eliminated |
| 12 | Denial of service | **Low risk** | Cooldown prevents rapid toggling; pause is owner-only |
| 13 | Gas griefing | **Low risk** | `rebalance()` public but deterministic |
| 14 | Storage collision | **N/A** | No proxy/upgradeable pattern |
| 15 | Uninitialized storage | **N/A** | All storage initialized in constructors |
| 16 | Delegate call injection | **N/A** | No delegatecall used |
| 17 | Signature replay | **N/A** | No signature-based auth |
| 18 | ERC-4626 inflation attack | **Mitigated** | Virtual shares/assets (1e6 offset) |
| 19 | ERC-4626 spec compliance | **Partial** | `previewWithdraw`/`previewRedeem` do not account for withdrawal fee (see M-5) |
| 20 | Token approval race condition | **N/A** | No approve patterns in core contracts |
| 21 | Access control bypass | **Mitigated** | All admin functions protected. `mint()` now has guards |
| 22 | Privilege escalation | **Low risk** | Two-step ownership prevents accidental transfer. No timelock |
| 23 | Emergency mechanism | **Pass** | `emergencyWithdraw` pulls LP and pauses. Withdrawals remain open |
| 24 | Centralization risk | **Medium risk** | Single owner with broad powers, no timelock |
| 25 | Cross-contract interaction | **Mitigated** | Callback pattern with `_pendingAction` enum; `onlyPoolManager` guards |
| 26 | State consistency | **Improved** | `deployedLiquidity` properly zeroed on removal; `setPoolKey` guarded by LP check |
| 27 | Event emission | **Fixed** | Events on all state changes in vault. `setLPRange` in hook still missing event (L-3) |
| 28 | Input validation | **Improved** | Bounds on twapThreshold, lambda, withdrawalFeeBps, maxSlippageBps, depositCap, tick alignment |
| 29 | External dependency risk | **Low risk** | Solmate (well-audited), v4-core (pre-release). LiquidityAmounts from test utils (M-4) |
| 30 | Fee mechanism | **Partial** | Fee now deducted from transfer (C-1 fixed), but accounting interacts with totalAssets (L-4) |
| 31 | Rounding errors | **Low risk** | mulDivDown/Up used appropriately in share math. Fee rounding favors vault |
| 32 | Token compatibility | **N/A for now** | Vault uses standard ERC20 tokens. Fee-on-transfer/rebasing tokens not supported |
| 33 | Block timestamp dependence | **Acceptable** | EWMA uses `block.timestamp` for elapsed time; within expected tolerance |
| 34 | Constructor safety | **Pass** | Hook validates permissions in constructor. Vault sets owner and keeper |
| 35 | Fallback/receive functions | **N/A** | No fallback/receive in production contracts (only in tests) |
| 36 | Self-destruct | **N/A** | No selfdestruct used |

---

## Part C: Guidelines Compliance Re-check

### Checks-Effects-Interactions in Withdraw/Redeem

**Status: PASS (Improved)**

The v1 concern was that `beforeWithdraw` performed external calls inside the ERC4626 flow. In v2:

1. `withdraw()` and `redeem()` are fully overridden -- they no longer delegate to solmate's internal flow.
2. The pattern in `withdraw()` is:
   - **Checks:** `_checkTWAP()`, allowance check
   - **Effects (partial):** `accumulatedFees += fee`
   - **Interactions:** `_ensureIdle(assets)` may call `_removeLiquidity()` (external call to PoolManager)
   - **Effects (continued):** `_burn(owner_, shares)`, emit event
   - **Interactions:** `asset.safeTransfer(receiver, assets - fee)`
3. The `_ensureIdle` call occurs before `_burn`, which means effects happen after an external interaction. However, the `nonReentrant` guard prevents re-entry, so the pattern is safe in practice even though it is not strictly CEI-ordered.

**Verdict:** Safe due to reentrancy guard. Strict CEI purists would note the interleaving, but it is functionally secure.

### Events on All State Changes

**Status: PASS (Fixed)**

All admin setters in `ILAlphaVault` now emit events:
- `KeeperUpdated`, `DepositCapUpdated`, `TwapThresholdUpdated`, `WithdrawalFeeUpdated`, `PoolKeyUpdated`, `PauseUpdated`
- `OwnershipTransferStarted`, `OwnershipTransferred`

Minor gap: `setLPRange` in `ILAlphaHook.sol` still does not emit an event (L-3). `setLambda` and `setKeeper` in hook also lack events (though keeper/lambda changes in the hook are less critical since the vault's events cover vault-side changes).

### Emergency Procedures

**Status: PASS**

- `emergencyWithdraw()` pulls all LP via `_removeLiquidity()` and sets `paused = true`
- Deposits and `rebalance()` blocked when paused
- Withdrawals remain open when paused (users can exit)
- `nonReentrant` guard on emergency function
- Only owner can trigger emergency
- `EmergencyWithdraw` event emitted with recovered balance

**One concern:** No emergency function on `ILAlphaHook` itself. If the hook malfunctions, there is no way to pause the hook independently (the vault can pause, but the hook's `afterSwap` will continue running for all swaps in the pool). This is low risk since the hook does not hold funds.

---

## Part D: Updated Overall Risk Assessment

### Risk Rating: **MEDIUM** (down from MEDIUM-HIGH in v1)

The four critical findings from v1 (C-1 through C-4) are all resolved. Most high-severity findings are fixed. The remaining issues are medium-severity design decisions (50/50 split, remove-side slippage, ERC-4626 fee spec compliance) and low-severity edge cases.

### Remaining Top 5 Findings

| Rank | ID | Severity | Finding | Exploitable? |
|------|-----|----------|---------|-------------|
| 1 | M-2 | MEDIUM | 50/50 asset split assumes vault holds both tokens | Yes -- revert or suboptimal LP at non-1:1 prices |
| 2 | M-1 | MEDIUM | `_executeRemoveLiquidity` lacks slippage protection | Yes -- MEV sandwich on removal, lower impact than add-side |
| 3 | M-5 | MEDIUM | Withdrawal fee breaks ERC-4626 `previewWithdraw`/`previewRedeem` accuracy | Yes -- integrator accounting errors |
| 4 | M-3 | MEDIUM | No timelock on critical parameter changes | Yes -- compromised owner instant exploitation |
| 5 | L-4 | LOW | Fee accounting interacts with totalAssets, socializing cost to depositors | Yes -- gradual share price dilution on fee claims |

### Updated Audit Readiness Score: 75/100 (up from 55/100 in v1)

| Category | v1 | v2 | Weight | Rationale |
|----------|:--:|:--:|:------:|-----------|
| Code quality | 8/10 | 8/10 | 20% | Clean, modular, well-structured. Fix annotations are helpful. |
| Security controls | 6/10 | 8/10 | 25% | All criticals fixed. TWAP now uses real accumulator. Slippage protection on add-side. Reentrancy guards complete. |
| Test coverage | 7/10 | 7/10 | 20% | Good unit + fuzz tests. Still missing invariant tests and explicit tests for new features (TWAP accumulator, slippage check, mint guards). |
| Documentation | 5/10 | 6/10 | 10% | Fix annotations added. Still no formal specification. |
| Access control | 7/10 | 8/10 | 15% | Two-step ownership, zero-address checks, bounds validation on all params. Still no timelock. |
| MEV resistance | 4/10 | 7/10 | 10% | Real TWAP, slippage protection, withdrawal fee. Removal-side gap remains. |

**Weighted score: 75/100**

### Recommendation: Conditionally Ready for Professional Audit

The codebase has matured significantly from v1. All 4 critical and 7 of 8 high-severity findings are resolved. The remaining issues are design-level decisions (50/50 split, fee spec compliance) that an audit firm would flag but not consider blockers.

**Before engaging auditors, address:**

1. **M-2 (50/50 split):** This is a functional limitation that will cause test failures with real token pairs. Either implement single-sided provision with pre-swap or clearly document as a known limitation with a concrete Phase 4 plan.
2. **M-5 (ERC-4626 fee compliance):** Override `previewWithdraw`/`previewRedeem` to include fee impact. Integrators will rely on these functions.
3. **Add invariant tests:** Auditors specifically look for property-based testing. Key invariants:
   - `totalAssets() >= sum of all depositor claims - fees`
   - `convertToAssets(convertToShares(x)) <= x` (rounding favors vault)
   - `deployedLiquidity == 0` after any `_removeLiquidity` call

**After those three items, the codebase would score ~82/100 and be well-positioned for professional audit.**

---

### Changelog: v1 to v2

| Area | Change |
|------|--------|
| `ILAlphaVault.withdraw/redeem` | Fully overridden with fee deduction, reentrancy guard, TWAP check |
| `ILAlphaVault.mint` | Overridden with all deposit guards |
| `ILAlphaVault.setPoolKey` | `LPStillDeployed` guard added |
| `ILAlphaVault.setTwapThreshold` | Bounds: 10-2000 ticks |
| `ILAlphaVault.totalAssets` | Only counts asset token from LP (H-7 fix) |
| `ILAlphaVault._checkSlippage` | New function for LP add operations |
| `ILAlphaVault._checkTWAP` | Now uses real TWAP from hook accumulator |
| `ILAlphaVault` events | 6 new events on admin setters |
| `ILAlphaVault.claimFees` | Caps at available balance |
| `ILAlphaHook.pushVolEstimate` | Rate limit 2x (was 4x), zero baseline capped to 1e18 |
| `ILAlphaHook._recordTickObservation` | New TWAP accumulator with circular buffer |
| `ILAlphaHook.getTwapTick` | New time-weighted average tick function |
| `ILAlphaHook.setLPRange` | Tick spacing alignment validation |
| `AlwaysLPVault` | Simplified to balance-only totalAssets (H-6 fix) |
| Zero-address checks | Added to setKeeper, transferOwnership, claimFees |
