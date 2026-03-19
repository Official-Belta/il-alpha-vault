# IL Alpha Vault -- Static Analysis Security Re-Audit (v2)

**Date:** 2026-03-20
**Auditor:** Manual static analysis (Trail of Bits methodology)
**Scope:** 6 Solidity files in `contracts/src/`
**Solidity Version:** ^0.8.26
**Baseline:** v1 audit (`docs/audit/01-static-analysis.md`, 22 findings: C-1 through I-5)

---

## Executive Summary

The v1 audit identified 22 findings. The development team applied fixes to the most critical issues. This re-audit verifies those fixes and identifies regressions and new issues introduced by the changes.

**Fix Verification Results:**

| Finding | Severity | Status |
|---------|----------|--------|
| C-1 | CRITICAL | FIXED (with caveats -- see R-1, R-2) |
| H-1 | HIGH | FIXED |
| H-2 | HIGH | PARTIALLY FIXED |
| H-3 | HIGH | NOT FIXED (acknowledged) |
| H-4 | HIGH | FIXED |
| M-1 | MEDIUM | FIXED (renamed C-3 in code) |
| M-2 | MEDIUM | NOT FIXED |
| M-3 | MEDIUM | FIXED |
| M-4 | MEDIUM | FIXED |
| M-5 | MEDIUM | NOT FIXED |
| M-6 | MEDIUM | NOT FIXED |
| L-1 | LOW | PARTIALLY FIXED |
| L-2 | LOW | FIXED (code removed) |
| L-3 | LOW | FIXED |
| L-4 | LOW | FIXED |
| L-5 | LOW | FIXED |
| L-6 | LOW | FIXED |
| I-1 | INFORMATIONAL | FIXED (renamed C-2 in code) |
| I-2 | INFORMATIONAL | N/A (no action needed) |
| I-3 | INFORMATIONAL | NOT FIXED |
| I-4 | INFORMATIONAL | N/A (accepted risk) |
| I-5 | INFORMATIONAL | N/A (accepted risk) |

**New Issues Found:** 6 (1 HIGH, 3 MEDIUM, 2 LOW)

---

## Part 1: v1 Finding Verification

### C-1: Withdrawal Fee Accounting Inflates `totalAssets`

**Status: FIXED**

**Evidence:** The `withdraw()` and `redeem()` functions are now fully overridden in `ILAlphaVault.sol` (lines 329-370). The fee is computed and added to `accumulatedFees`, and only `assets - fee` is transferred to the receiver:

- `withdraw()` line 346: `asset.safeTransfer(receiver, assets - fee);`
- `redeem()` line 369: `asset.safeTransfer(receiver, assets - fee);`

The `beforeWithdraw()` override (line 388) is intentionally empty; all logic is in the overrides. The parent `ERC4626.withdraw()`/`redeem()` are no longer called -- the vault handles burning, allowance checks, and transfer itself.

**Caveats:** See new findings R-1 and R-2 for regressions introduced by this fix.

---

### H-1: TWAP Oracle Manipulation -- `lastTick` Is Not a True TWAP

**Status: FIXED**

**Evidence:** `ILAlphaHook.sol` now implements a proper TWAP via a circular buffer:

- `TickObservation` struct (lines 99-102) stores tick + timestamp pairs.
- `tickObservations` mapping (line 114): fixed-size array of 10 observations per pool.
- `_recordTickObservation()` (lines 448-455): records each swap's tick in the circular buffer.
- `getTwapTick()` (lines 459-481): computes a recency-weighted average tick, ignoring observations older than 1 hour.
- `_checkTWAP()` in `ILAlphaVault.sol` (lines 414-430) now calls `hook.getTwapTick(poolId)` instead of using raw `lastTick`.

The TWAP is no longer trivially manipulable by a single swap. An attacker would need to sustain manipulation across multiple swaps over time to shift the TWAP.

**See R-3 for a remaining concern with the TWAP implementation.**

---

### H-2: Unprotected `rebalance()` Enables Sandwich Attack on LP Add/Remove

**Status: PARTIALLY FIXED**

**Evidence:** A slippage check was added via `_checkSlippage()` (line 373-377):

```solidity
function _checkSlippage(int128 d0, int128 d1, uint256 expected) internal view {
    uint256 actualCost = (d0 < 0 ? uint256(uint128(-d0)) : 0) + (d1 < 0 ? uint256(uint128(-d1)) : 0);
    uint256 maxCost = expected + (expected * maxSlippageBps) / 10_000;
    if (actualCost > maxCost) revert SlippageExceeded();
}
```

Called at line 274 in `_executeAddLiquidity`. The `maxSlippageBps` is configurable (default 100 = 1%, max 500 = 5%).

**Remaining issues:**
- `rebalance()` is still permissionless. The slippage check limits damage but does not prevent a MEV bot from triggering rebalance at unfavorable timing.
- `_checkSlippage` is only called on `_executeAddLiquidity`, NOT on `_executeRemoveLiquidity` (line 312-323). Removals have no slippage protection.
- The slippage check sums both token costs, which conflates the two tokens. If one token's cost is high and the other is low, the aggregate can still pass while one side suffers significant slippage.

---

### H-3: `_executeAddLiquidity` Naive 50/50 Split Wastes Tokens

**Status: NOT FIXED (acknowledged)**

**Evidence:** `_computeLiquidity()` (lines 281-292) still passes `assets / 2, assets / 2` to `getLiquidityForAmounts`. The code comment at line 280 says: `H-3 NOTE: 50/50 split assumes vault holds both tokens. Phase 4: pre-swap.` This indicates the team acknowledges the issue and plans to fix it in a future phase.

---

### H-4: Keeper Can Manipulate Vol Oracle via `pushVolEstimate`

**Status: FIXED**

**Evidence:** `ILAlphaHook.sol` line 385 now reads:
```solidity
uint256 maxExternal = currentVar == 0 ? uint256(1e18) : currentVar * 2;
```

The rate limit is now correctly 2x (matching documentation), and the zero-baseline case is capped at `1e18` rather than `type(uint128).max`. Comment at line 383: `H-4 FIX: rate limit to 2x (not 4x), cap zero baseline to 1e18`.

---

### M-1: `setPoolKey` Can Be Called While Liquidity Is Deployed

**Status: FIXED**

**Evidence:** `ILAlphaVault.sol` line 481:
```solidity
if (deployedLiquidity > 0) revert LPStillDeployed();
```

Comment references `C-3 FIX`. The guard prevents changing the pool key while liquidity is deployed.

Additionally, the fix validates that the asset token is one of the pool's currencies (lines 483-486):
```solidity
if (
    Currency.unwrap(_poolKey.currency0) != assetAddr &&
    Currency.unwrap(_poolKey.currency1) != assetAddr
) revert InvalidPoolKey();
```

---

### M-2: `_executeRemoveLiquidity` Uses Stale Tick Range from Hook

**Status: NOT FIXED**

**Evidence:** `_executeRemoveLiquidity()` (line 312-323) still fetches the tick range from `hook.getPoolStrategy(poolKey)` at line 313. If `setLPRange()` was called after liquidity was added, the stored range will differ from the deployed range, causing the removal to fail or return zero tokens.

The vault does not store the tick range used at deployment time.

---

### M-3: No Tick Spacing Alignment Validation in `setLPRange`

**Status: FIXED**

**Evidence:** `ILAlphaHook.sol` lines 412-413:
```solidity
int24 spacing = key.tickSpacing;
require(tickLower % spacing == 0 && tickUpper % spacing == 0, "Tick not aligned to spacing");
```

---

### M-4: `afterInitialize` Tick Rounding Can Produce `tickLower == tickUpper`

**Status: FIXED**

**Evidence:** `ILAlphaHook.sol` line 181:
```solidity
if (lower >= upper) upper = lower + spacing;
```

---

### M-5: `_updateVolOracle` Short-Elapsed Noise Amplification

**Status: NOT FIXED**

**Evidence:** `_updateVolOracle()` (lines 299-322) still computes `squaredReturn = (squaredReturn * 3600) / elapsed`. For `elapsed = 1` second, a 1-tick move is amplified 3600x. No minimum elapsed threshold or cap is applied. The guard only catches `elapsed == 0` (same-block).

---

### M-6: `SwapHelper` Lacks Reentrancy Guard and Uses Unsafe `transferFrom`

**Status: NOT FIXED**

**Evidence:** `SwapHelper.sol` still uses `safeTransferFrom` from solmate (which is safe), but the `unlockCallback` (line 65) does not clear pending state variables after use. The `_locked` guard in `swap()` and `addLiquidity()` provides reentrancy protection for external calls, but the callback itself does not re-verify `_locked`.

Note: `SwapHelper` is a testnet utility. The risk is low for production.

---

### L-1: `AlwaysLPVault.rebalance()` Has No Access Control

**Status: PARTIALLY FIXED**

**Evidence:** The `AlwaysLPVault` (lines 12-37) was significantly simplified. It no longer tracks `deployedAssets` -- `totalAssets()` simply returns `asset.balanceOf(address(this))` (line 30). The `rebalance()` function is still permissionless (line 34), but now only emits an event with no state mutation, making the access control issue moot.

---

### L-2: `AlwaysLPVault.beforeWithdraw` Sets `deployedAssets = 0` Unconditionally

**Status: FIXED (code removed)**

**Evidence:** The `AlwaysLPVault` no longer has a `beforeWithdraw` override or `deployedAssets` variable. The entire `deployedAssets` tracking was removed as part of the H-6 fix (referenced in the comment at line 9).

---

### L-3: No Event Emission for Admin State Changes

**Status: FIXED**

**Evidence:** `ILAlphaVault.sol` now emits events for:
- `KeeperUpdated` (line 497)
- `DepositCapUpdated` (line 502)
- `TwapThresholdUpdated` (line 509)
- `WithdrawalFeeUpdated` (line 520)
- `PauseUpdated` (line 492)
- `PoolKeyUpdated` (line 487 -- though this event carries no data)

---

### L-4: `transferOwnership` Allows Setting `pendingOwner` to `address(0)`

**Status: FIXED**

**Evidence:** Both `ILAlphaHook.sol` line 486 and `ILAlphaVault.sol` line 467:
```solidity
require(newOwner != address(0), "Zero address");
```

---

### L-5: `setKeeper` Does Not Validate Against `address(0)`

**Status: FIXED**

**Evidence:** Both `ILAlphaHook.sol` line 499 and `ILAlphaVault.sol` line 496:
```solidity
require(_keeper != address(0), "Zero address");
```

---

### L-6: `claimFees` Transfers Without Checking Balance

**Status: FIXED**

**Evidence:** `ILAlphaVault.sol` lines 524-533:
```solidity
uint256 available = asset.balanceOf(address(this));
uint256 claimable = fees > available ? available : fees;
accumulatedFees = fees - claimable;
asset.safeTransfer(to, claimable);
```

The `min(fees, available)` logic correctly handles the case where the vault balance is insufficient. Partial claims are now possible, with remaining fees tracked for future claims.

---

### I-1: `ILAlphaVault.deposit` Does Not Override `mint()`

**Status: FIXED**

**Evidence:** `ILAlphaVault.sol` lines 184-196 add a `mint()` override with identical guards:
- `whenNotPaused`
- `nonReentrant`
- `DepositTooSmall` check (via `previewMint` conversion)
- `DepositCapExceeded` check
- `_checkTWAP()`

---

### I-2: Solidity ^0.8.26 Provides Built-in Overflow Protection

**Status: N/A** -- Informational, no action needed.

---

### I-3: `getVolEstimate` Annualization Is Simplified

**Status: NOT FIXED**

**Evidence:** `ILAlphaHook.sol` line 424 still returns `annualizedVol = uint256(hourlyVar) * 8760`. The name remains `annualizedVol` despite being variance. This is cosmetic.

---

### I-4: `HODLVault` Has No Owner or Admin Functions

**Status: N/A** -- Accepted risk for control vault.

---

### I-5: `ILAlphaHook` Storage Layout Not Upgrade-Safe

**Status: N/A** -- Accepted risk; contract is not designed as upgradeable.

---

## Part 2: New Issues (Regressions and Newly Discovered)

### R-1 [HIGH]: `withdraw()` Override Burns Shares for Gross Amount But Transfers Net Amount -- User Overpays

**File:** `ILAlphaVault.sol`, lines 329-347
**Severity:** HIGH

**Description:**
The `withdraw()` override computes shares to burn via `previewWithdraw(assets)` (line 339), which returns the number of shares needed to withdraw `assets` worth of value. The user specifies they want to withdraw `assets`, the vault burns shares worth `assets`, but then only transfers `assets - fee` to the receiver. The user loses `fee` worth of value with no recourse.

This is the intended design for a withdrawal fee, but the ERC-4626 standard specifies that `withdraw(assets, ...)` should result in the receiver getting exactly `assets` tokens. The current implementation violates ERC-4626 semantics: the receiver gets fewer tokens than `assets`, but `assets` worth of shares are burned.

Furthermore, there is an accounting inconsistency: `accumulatedFees` is incremented by `fee`, and this amount stays in the vault's `asset.balanceOf()`. This means `totalAssets()` includes the fee as idle balance, inflating the share price for remaining holders. When the owner calls `claimFees()`, the share price drops. This creates a subtle sandwiching opportunity: deposit before fee claim, withdraw after.

**Impact:** Users receive fewer tokens than the ERC-4626 `withdraw()` interface promises. The fee retained in the vault temporarily inflates `totalAssets()` until claimed, creating arbitrage between deposit-before-claim and withdraw-after-claim.

**Recommended Fix:**
Option A (preserve ERC-4626 semantics): Burn shares worth `assets + fee`, transfer `assets` to receiver. This requires computing `grossAssets = assets * 10_000 / (10_000 - withdrawalFeeBps)` and burning `previewWithdraw(grossAssets)` shares.

Option B (document deviation): Clearly document that `withdraw()` deviates from ERC-4626 and the receiver gets `assets - fee`. Override `maxWithdraw()` and `previewWithdraw()` to account for the fee so integrators get correct estimates. Exclude `accumulatedFees` from `totalAssets()` by subtracting it:
```solidity
function totalAssets() public view override returns (uint256) {
    uint256 idle = asset.balanceOf(address(this)) - accumulatedFees;
    // ...
}
```

---

### R-2 [MEDIUM]: `withdraw()` and `redeem()` Skip `super.withdraw()`/`super.redeem()` But Re-implement Allowance Logic -- Potential Inconsistency

**File:** `ILAlphaVault.sol`, lines 329-370
**Severity:** MEDIUM

**Description:**
Both `withdraw()` and `redeem()` re-implement the allowance checking and burning logic that normally lives in the parent `ERC4626` contract. This introduces a maintenance risk: if the parent contract's logic changes (e.g., different allowance patterns), the vault's overrides will be out of sync.

More concretely, the `withdraw()` override emits `Withdraw(msg.sender, receiver, owner_, assets, shares)` at line 345. The `assets` parameter in the event is the gross amount (before fee deduction), but the receiver only gets `assets - fee`. Off-chain indexers relying on the `Withdraw` event to track actual transfers will have incorrect data.

**Impact:** Off-chain monitoring and integrations that rely on the `Withdraw` event will overstate actual transfers. Future parent contract upgrades may introduce silent inconsistencies.

**Recommended Fix:**
Emit the event with the net amount (`assets - fee`) as the `assets` parameter, or emit a separate `WithdrawalFeeCharged(address owner, uint256 fee)` event for clarity.

---

### R-3 [MEDIUM]: TWAP Tick Accumulator Can Be Gamed via High-Frequency Small Swaps

**File:** `ILAlphaHook.sol`, lines 448-481
**Severity:** MEDIUM

**Description:**
The TWAP implementation uses a circular buffer of 10 observations, weighted by recency (newer = higher weight). An attacker can fill all 10 slots within a few blocks by executing 10+ small swaps, each recording the manipulated tick. Since the weighting is `3600 - age` and the attacker's swaps will all have very recent timestamps (within seconds), they will dominate the TWAP calculation.

Example attack:
1. Execute a large swap to move the tick to a manipulated value.
2. Execute 10 small dust swaps to fill the circular buffer with the manipulated tick, each in the same or consecutive blocks.
3. The TWAP is now dominated by these recent manipulated observations.
4. Deposit or withdraw at the manipulated TWAP-approved price.

The `TWAP_WINDOW = 10` is too small to resist this. Additionally, `_recordTickObservation` records one observation per swap regardless of size, so dust swaps have the same weight as large swaps.

**Impact:** The TWAP oracle can be manipulated with ~10 small swaps in rapid succession, partially negating the H-1 fix.

**Recommended Fix:**
- Increase `TWAP_WINDOW` to at least 30-60 observations.
- Weight observations by swap volume (larger swaps contribute more to the TWAP).
- Add a minimum time gap between observations (e.g., only record if `block.timestamp > lastObservationTimestamp + MIN_GAP`).
- Consider using Uniswap V4's built-in oracle if available.

---

### R-4 [MEDIUM]: `_checkSlippage` Not Called on `_executeRemoveLiquidity`

**File:** `ILAlphaVault.sol`, lines 312-323
**Severity:** MEDIUM

**Description:**
The `_checkSlippage` function is only invoked in `_executeAddLiquidity` (line 274) but not in `_executeRemoveLiquidity` (lines 312-323). A sandwich attacker can manipulate the price before a `rebalance()` that triggers liquidity removal, causing the vault to receive fewer tokens than expected.

The `_ensureIdle` function (line 380-385), called during `withdraw()` and `redeem()`, also triggers `_removeLiquidity()` without slippage protection.

**Impact:** LP removal operations are vulnerable to sandwich attacks. An attacker can trigger removal via `rebalance()` or by being the first withdrawer after LP is deployed.

**Recommended Fix:**
Add slippage checking to `_executeRemoveLiquidity`:
```solidity
function _executeRemoveLiquidity() internal {
    // ... existing code ...
    _settleDelta(delta);
    // Check that we received reasonable value back
    uint256 received = (d0 > 0 ? uint256(uint128(d0)) : 0) + (d1 > 0 ? uint256(uint128(d1)) : 0);
    // Compare against expected value from _getDeployedLPValue()
    deployedLiquidity = 0;
}
```

---

### R-5 [LOW]: `mint()` Override Computes `assets` Twice -- Wasted Gas

**File:** `ILAlphaVault.sol`, lines 184-196
**Severity:** LOW

**Description:**
The `mint()` override computes `assets = previewMint(shares)` at line 191 for the guard checks, then calls `super.mint(shares, receiver)` at line 195, which internally calls `previewMint(shares)` again. This is a minor gas waste (~2600 gas for the extra `totalAssets()` call which reads `asset.balanceOf` + potentially pool state).

**Impact:** Minor gas inefficiency, no correctness issue.

**Recommended Fix:**
Fully override `mint()` (like `withdraw()`/`redeem()`) to avoid the double computation. Or accept the gas cost for code clarity.

---

### R-6 [LOW]: `PoolKeyUpdated` Event Carries No Data

**File:** `ILAlphaVault.sol`, line 67 (declaration), line 487 (emission -- inferred from `setPoolKey`)
**Severity:** LOW

**Description:**
The `PoolKeyUpdated` event is declared with no parameters (line 67: `event PoolKeyUpdated()`). When emitted in `setPoolKey`, off-chain consumers cannot determine which pool was set without reading the contract state. This makes monitoring and incident response harder.

**Impact:** Reduced off-chain observability.

**Recommended Fix:**
Include the pool ID or relevant pool key fields in the event.

---

## Part 3: Remaining Issues Not Caught in v1

### N-1 [MEDIUM]: `accumulatedFees` Not Excluded from `totalAssets()` -- Share Price Inflation

**File:** `ILAlphaVault.sol`, lines 152-168, 335, 364
**Severity:** MEDIUM (overlaps with R-1 but is a distinct accounting issue)

**Description:**
When withdrawal fees are collected, `accumulatedFees` is incremented and the fee amount remains in the vault's `asset.balanceOf(address(this))`. Since `totalAssets()` includes the full idle balance (line 153: `uint256 idle = asset.balanceOf(address(this))`), the accumulated fees inflate `totalAssets()`, which inflates the share price.

This means:
1. User A deposits 1000 USDC, gets X shares.
2. User B deposits 1000 USDC, gets X shares.
3. User A withdraws 1000 USDC, pays 1 USDC fee (0.1%). Vault now holds 1001 USDC, but 1 USDC is "reserved" as accumulated fees.
4. User B's shares are now worth slightly more than 1000 USDC (because `totalAssets()` = 1001).
5. Owner claims 1 USDC fee. `totalAssets()` drops to 1000. User B's share price drops.

The fee acts as a temporary donation to remaining shareholders, then gets clawed back on claim. This is economically inconsistent and can be exploited by depositing right before a large fee claim.

**Impact:** Temporary share price inflation between fee accrual and claim. Sophisticated depositors can profit by timing deposits around fee claims.

**Recommended Fix:**
Subtract `accumulatedFees` from idle balance in `totalAssets()`:
```solidity
uint256 idle = asset.balanceOf(address(this)) - accumulatedFees;
```

---

### N-2 [LOW]: `_ensureIdle` Removes All Liquidity Even If Partial Would Suffice

**File:** `ILAlphaVault.sol`, lines 380-385
**Severity:** LOW

**Description:**
When a withdrawal needs more idle balance, `_ensureIdle` calls `_removeLiquidity()` which removes ALL deployed liquidity. If only a fraction was needed, the entire position is closed unnecessarily. This creates unnecessary gas costs and IL realization.

**Impact:** Gas inefficiency and forced full LP exit on any withdrawal that exceeds idle balance.

**Recommended Fix:**
Implement partial liquidity removal proportional to the deficit.

---

### N-3 [INFO]: `setPoolKey` Does Not Emit Pool Key Details

**File:** `ILAlphaVault.sol`, line 479-488
**Severity:** INFORMATIONAL

**Description:**
Although `PoolKeyUpdated` event was added (fixing L-3), it contains no parameters. The old pool key and new pool key are not emitted, making it impossible for off-chain monitoring to detect which pool changed without reading contract state.

(Duplicate of R-6, listed here for completeness in the "remaining issues" section.)

---

## Summary of New Findings

| ID | Severity | File | Description |
|----|----------|------|-------------|
| R-1 | HIGH | ILAlphaVault.sol:329-347 | `withdraw()` burns shares for gross amount but transfers net -- ERC-4626 violation and fee inflation |
| R-2 | MEDIUM | ILAlphaVault.sol:329-370 | `Withdraw` event emits gross amount, not net; maintenance risk from re-implemented logic |
| R-3 | MEDIUM | ILAlphaHook.sol:448-481 | TWAP buffer can be filled with 10 small swaps to manipulate the oracle |
| R-4 | MEDIUM | ILAlphaVault.sol:312-323 | No slippage check on `_executeRemoveLiquidity` |
| R-5 | LOW | ILAlphaVault.sol:184-196 | `mint()` override computes `previewMint` twice |
| R-6 | LOW | ILAlphaVault.sol:67 | `PoolKeyUpdated` event has no parameters |
| N-1 | MEDIUM | ILAlphaVault.sol:152-168 | `accumulatedFees` not excluded from `totalAssets()` inflates share price |
| N-2 | LOW | ILAlphaVault.sol:380-385 | `_ensureIdle` removes all LP even if partial removal suffices |

---

## Appendix: Files Reviewed

| File | Lines | v1 Findings | Status |
|------|-------|-------------|--------|
| `ILAlphaHook.sol` | 507 | H-4, M-3, M-4, M-5, L-4, L-5, I-3, I-5 | 4 fixed, 2 not fixed, 2 N/A |
| `ILAlphaVault.sol` | 543 | C-1, H-1, H-2, H-3, M-1, M-2, L-3, L-4, L-5, L-6, I-1 | 8 fixed, 2 not fixed, 1 partial |
| `BaseVault.sol` | 53 | I-2 | N/A |
| `SwapHelper.sol` | 143 | M-6 | Not fixed |
| `AlwaysLPVault.sol` | 37 | L-1, L-2 | 1 fixed, 1 partial |
| `HODLVault.sol` | 19 | I-4 | N/A |
