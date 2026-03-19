# IL Alpha Vault -- Static Analysis Security Audit

**Date:** 2026-03-20
**Auditor:** Manual static analysis (Trail of Bits methodology)
**Scope:** 6 Solidity files in `contracts/src/`
**Solidity Version:** ^0.8.26 (overflow-checked by default)

---

## Summary

| Severity      | Count |
|---------------|-------|
| CRITICAL      | 1     |
| HIGH          | 4     |
| MEDIUM        | 6     |
| LOW           | 6     |
| INFORMATIONAL | 5     |
| **Total**     | **22**|

---

## CRITICAL

### C-1: Withdrawal Fee Accounting Inflates `totalAssets`, Causing Permanent Share Price Corruption

**File:** `ILAlphaVault.sol`, lines 299-312
**Severity:** CRITICAL

**Description:**
The `beforeWithdraw` hook increments `accumulatedFees` but never actually deducts those fees from the withdrawn assets or from the vault's accounting. The fee is added to `accumulatedFees` (line 305), but the full `assets` amount is still transferred to the withdrawer by the parent ERC-4626 `withdraw()` implementation. Meanwhile, `claimFees()` (line 434-438) transfers tokens from the vault's balance using `asset.safeTransfer`, reducing the actual balance.

This creates a double-spend scenario:
1. User withdraws `assets` (gets the full amount -- fee is not deducted from the transfer).
2. `accumulatedFees` is incremented by `fee`.
3. Owner calls `claimFees()`, which transfers `fee` from the vault balance.
4. The vault's actual token balance is now less than what `totalAssets()` reports via share accounting, since those fee tokens were counted as part of the vault but also given to the withdrawer.

The result is that `totalAssets()` becomes inflated relative to actual holdings, causing remaining depositors to receive fewer tokens on withdrawal than their shares entitle them to.

**Impact:** Loss of funds for remaining depositors. The owner can extract fees that effectively come out of other depositors' principal.

**Recommended Fix:**
Either (a) deduct the fee from the amount transferred to the withdrawer, or (b) track fees as a separate accounting entry that is excluded from `totalAssets()`. Example:

```solidity
function beforeWithdraw(uint256 assets, uint256) internal override {
    _checkTWAP();
    if (withdrawalFeeBps > 0) {
        uint256 fee = (assets * withdrawalFeeBps) / 10_000;
        accumulatedFees += fee;
        // The parent withdraw() sends `assets` to the user.
        // We need to ensure the fee is retained. Override afterDeposit
        // or modify the withdrawal to send (assets - fee).
    }
    // ...
}
```

Alternatively, override `withdraw()` fully to send `assets - fee` to the receiver and keep `fee` in the vault.

---

## HIGH

### H-1: TWAP Oracle Manipulation -- `lastTick` Is Not a True TWAP

**File:** `ILAlphaVault.sol`, lines 337-355
**Severity:** HIGH

**Description:**
The `_checkTWAP()` function uses the hook's `volOracles[poolId].lastTick` as a proxy for historical price. However, `lastTick` is simply the tick observed during the most recent swap (updated in `_updateVolOracle`, line 300 of `ILAlphaHook.sol`). An attacker can:

1. Execute a swap to set `lastTick` to the manipulated price.
2. In the same or next block, execute the deposit/withdraw at the manipulated price.

Since `lastTick` is just the most recent swap tick, it provides no meaningful time-weighted average protection. A multi-block attacker can set both `spotTick` and `lastTick` to the same manipulated value, bypassing the check entirely.

**Impact:** The TWAP manipulation guard is ineffective. Deposit/withdrawal sandwich attacks are possible, allowing an attacker to extract value from the vault by manipulating the price used in `totalAssets()` computation.

**Recommended Fix:**
Implement a proper TWAP using a tick accumulator or integrate an external oracle (e.g., Chainlink). At minimum, use a multi-observation ring buffer with time-weighting.

---

### H-2: Unprotected `rebalance()` Enables Sandwich Attack on LP Add/Remove

**File:** `ILAlphaVault.sol`, lines 176-196
**Severity:** HIGH

**Description:**
The `rebalance()` function is permissionless (`external whenNotPaused nonReentrant`). While the comment states "Result is deterministic (hook signal only)", the actual LP add/remove operations are price-dependent. An attacker can:

1. Manipulate pool price (push it to edge of tick range).
2. Call `rebalance()` to force the vault to add liquidity at a skewed price, getting unfavorable amounts.
3. Reverse the price manipulation, profiting from the vault's IL.

The 50/50 asset split in `_executeAddLiquidity` (lines 234-235) is especially vulnerable: if the price is manipulated, one side of the split may be almost entirely wasted.

**Impact:** MEV extraction from the vault during rebalance operations. Vault depositors suffer losses.

**Recommended Fix:**
Add slippage protection parameters to `rebalance()`, or restrict it to keeper-only. Additionally, add minimum liquidity checks and consider computing optimal token ratios based on current price rather than a naive 50/50 split.

---

### H-3: `_executeAddLiquidity` Naive 50/50 Split Wastes Tokens

**File:** `ILAlphaVault.sol`, lines 233-235
**Severity:** HIGH

**Description:**
The vault splits idle assets 50/50 between token0 and token1:
```solidity
uint256 amount0 = assets / 2;
uint256 amount1 = assets / 2;
```

This assumes:
- Both tokens have the same decimals.
- The price ratio is 1:1.

In practice, if the vault's `asset` is USDC (6 decimals) and the other token is WETH (18 decimals), or if the price ratio deviates from 1:1, a significant portion of tokens will be left unused after `getLiquidityForAmounts`. These unused tokens are sent to the PoolManager via `_settleCurrency` but may not all be consumed, leading to stranded tokens in the PoolManager or incorrect settlement.

Furthermore, the vault only holds the `asset` token (validated in `setPoolKey`), so it has no tokens of the counter-currency to provide. The `_settleCurrency` call for the non-asset token will revert or transfer zero.

**Impact:** Liquidity provisioning will fail or be highly capital-inefficient. Possible loss of funds if settlement succeeds with incorrect amounts.

**Recommended Fix:**
Implement a swap to convert the appropriate portion of the asset into the counter-currency before providing liquidity. Use the actual price to compute the correct ratio. Add slippage bounds.

---

### H-4: Keeper Can Manipulate Vol Oracle via `pushVolEstimate` to Force LP Toggle

**File:** `ILAlphaHook.sol`, lines 359-377
**Severity:** HIGH

**Description:**
The `pushVolEstimate` rate limit allows changes up to 4x the current value when `currentVar != 0` (line 366). The comment says "max change per push is 2x" but the code sets `maxExternal = currentVar * 4`. When `currentVar == 0`, any value up to `type(uint128).max` is accepted (line 366).

A compromised keeper key can:
1. When `ewmaVar == 0` (fresh pool or post-reset), push an arbitrarily large vol estimate.
2. Even with a non-zero base, repeatedly push 4x values across multiple calls to exponentially inflate variance.
3. This forces `ilCost` to exceed `feeYield`, toggling LP off (or keeping it off).

The blending is only 50/50 (`(currentVar + externalVar) / 2`), so each push can approximately double the current variance. A sequence of pushes can escalate rapidly.

**Impact:** A compromised keeper can manipulate the LP strategy, forcing liquidity removal at disadvantageous times. Combined with sandwich attacks, this enables profit extraction.

**Recommended Fix:**
- Fix the rate limit to match the documented 2x cap: `maxExternal = currentVar * 2`.
- Add a per-block or time-based rate limit for `pushVolEstimate` calls.
- Consider a multisig or timelock for keeper operations.

---

## MEDIUM

### M-1: `setPoolKey` Can Be Called While Liquidity Is Deployed, Causing Orphaned Position

**File:** `ILAlphaVault.sol`, lines 403-411
**Severity:** MEDIUM

**Description:**
The owner can call `setPoolKey()` to change the pool while `deployedLiquidity > 0`. After the change, the vault's `deployedLiquidity` state still references the old pool, but all subsequent operations (rebalance, totalAssets, withdraw) will use the new pool key. The old LP position becomes unrecoverable through the vault's interface.

**Impact:** Permanent loss of deployed liquidity if the owner changes the pool key while a position is active.

**Recommended Fix:**
```solidity
function setPoolKey(PoolKey calldata _poolKey) external onlyOwner {
    require(deployedLiquidity == 0, "Must remove liquidity first");
    // ... existing validation
}
```

---

### M-2: `_executeRemoveLiquidity` Uses Stale Tick Range from Hook

**File:** `ILAlphaVault.sol`, lines 275-295
**Severity:** MEDIUM

**Description:**
When removing liquidity, the function fetches the current tick range from `hook.getPoolStrategy()` (line 276). If the owner has called `hook.setLPRange()` since the position was created, the tick range will differ from the range where liquidity was actually deployed. The `modifyLiquidity` call will try to remove liquidity from a range where none exists, resulting in either a revert or zero tokens returned.

**Impact:** Liquidity becomes stuck and unrecoverable if the LP range is changed after deployment.

**Recommended Fix:**
Store the tick range used when liquidity was added (in the vault contract), and use those stored values when removing liquidity. Only use the hook's range for new positions.

---

### M-3: No Tick Spacing Alignment Validation in `setLPRange`

**File:** `ILAlphaHook.sol`, lines 390-395
**Severity:** MEDIUM

**Description:**
The `setLPRange` function validates `tickLower < tickUpper` but does not validate that the ticks are aligned to the pool's `tickSpacing`. Uniswap V4's `modifyLiquidity` requires tick alignment; unaligned ticks will cause reverts when the vault tries to add or remove liquidity.

**Impact:** Owner can set an invalid tick range that bricks the vault's LP operations until corrected.

**Recommended Fix:**
```solidity
function setLPRange(PoolKey calldata key, int24 tickLower, int24 tickUpper) external onlyOwner {
    if (tickLower >= tickUpper) revert InvalidTickRange();
    if (tickLower % key.tickSpacing != 0 || tickUpper % key.tickSpacing != 0) revert InvalidTickRange();
    // ...
}
```

---

### M-4: `afterInitialize` Tick Rounding Can Produce `tickLower == tickUpper`

**File:** `ILAlphaHook.sol`, lines 163-166
**Severity:** MEDIUM

**Description:**
The tick range calculation uses integer division truncation:
```solidity
int24 lower = ((tick - halfRange) / spacing) * spacing;
int24 upper = ((tick + halfRange) / spacing) * spacing;
```

For pools with large `tickSpacing` (e.g., 200), if `halfRange = 500`, the rounded lower and upper could be equal (e.g., tick=0, spacing=1000 yields lower=0, upper=0). A zero-width range makes LP operations impossible.

**Impact:** Pool initialization with certain tick spacings produces a degenerate configuration, preventing LP entirely.

**Recommended Fix:**
After rounding, verify `lower < upper`. If they are equal, add `spacing` to `upper`:
```solidity
if (lower >= upper) upper = lower + spacing;
```

---

### M-5: `_updateVolOracle` Division by Zero When `elapsed == 0` Guard Is Bypassed

**File:** `ILAlphaHook.sol`, line 292
**Severity:** MEDIUM

**Description:**
The guard `if (elapsed == 0) return;` protects against same-block swaps. However, the `uint40` timestamp truncation (line 301) means that if `block.timestamp` wraps around modulo 2^40 (year ~36812), `elapsed` could underflow. While impractical today, the `uint40` type also means `block.timestamp - vo.lastTimestamp` could produce a very large value if `lastTimestamp` is somehow set to a future value (e.g., via keeper manipulation on a chain with non-standard timestamps), making `squaredReturn` division by `elapsed` approach zero and suppressing vol detection.

More practically, the division `(squaredReturn * 3600) / elapsed` on line 292 normalizes to per-hour. For very short elapsed times (1-2 seconds), this amplifies noise enormously: a 1-tick move in 1 second becomes 3600x the per-hour variance contribution. This can cause vol spikes from normal trading, leading to false positive LP toggles.

**Impact:** Vol oracle noise amplification for rapid consecutive swaps across blocks.

**Recommended Fix:**
Add a minimum elapsed time threshold (e.g., 10 seconds) before updating the oracle, or cap the time-normalized return.

---

### M-6: `SwapHelper` Lacks Reentrancy Guard and Uses Unsafe `transferFrom`

**File:** `SwapHelper.sol`, lines 55-98, 82, 89
**Severity:** MEDIUM

**Description:**
1. The `unlockCallback` has no reentrancy protection. While the PoolManager callback pattern provides some implicit safety, the state variables (`_pendingKey`, `_pendingZeroForOne`, `_pendingAmount`, `_isSwap`) are not cleared before executing the callback logic.
2. Uses `ERC20.transferFrom()` (lines 82, 89) without checking the return value. While solmate's `ERC20` reverts on failure for compliant tokens, non-standard tokens (USDT, etc.) that return false instead of reverting will silently fail.

**Impact:** For testnet use this is lower risk, but in production, token transfers could silently fail, leaving the PoolManager in an inconsistent settlement state.

**Recommended Fix:**
Use `SafeTransferLib.safeTransferFrom()` instead of raw `transferFrom()`. Clear pending state variables after use.

---

## LOW

### L-1: `AlwaysLPVault.rebalance()` Has No Access Control

**File:** `controls/AlwaysLPVault.sol`, lines 33-40
**Severity:** LOW

**Description:**
The `rebalance()` function is fully public with no access control. Anyone can call it to add idle assets to `deployedAssets`. While this is a control vault, the `deployedAssets` accounting is only virtual (no actual LP interaction), making this a bookkeeping-only issue. However, it means anyone can trigger the "deployed" state transition.

**Impact:** Minor -- control vault only. No real funds at risk since `deployedAssets` is just an accounting variable.

**Recommended Fix:**
Add `onlyOwner` modifier for consistency: `function rebalance() external onlyOwner`.

---

### L-2: `AlwaysLPVault.beforeWithdraw` Sets `deployedAssets = 0` Unconditionally

**File:** `controls/AlwaysLPVault.sol`, lines 42-47
**Severity:** LOW

**Description:**
When a withdrawal requires more than idle balance, the vault sets `deployedAssets = 0` regardless of how much was actually needed. If a user withdraws a small amount, all `deployedAssets` are "undeployed", which may distort the control experiment's accounting.

**Impact:** Inaccurate accounting in the control vault; does not affect real funds.

**Recommended Fix:**
Deduct only the needed amount: `deployedAssets -= (assets - idle);`

---

### L-3: No Event Emission for Admin State Changes

**File:** `ILAlphaVault.sol`, lines 413-432
**Severity:** LOW

**Description:**
The functions `setPaused`, `setKeeper`, `setDepositCap`, `setTwapThreshold`, and `setWithdrawalFeeBps` change critical protocol parameters but emit no events. This makes off-chain monitoring and incident response more difficult.

**Impact:** Reduced auditability and monitoring capability.

**Recommended Fix:**
Emit events for all admin state changes.

---

### L-4: `transferOwnership` Allows Setting `pendingOwner` to `address(0)`

**File:** `ILAlphaHook.sol`, line 427; `ILAlphaVault.sol`, line 392
**Severity:** LOW

**Description:**
Both contracts allow `transferOwnership(address(0))`. If `acceptOwnership()` were somehow called by address(0) (impossible in practice for EOAs but possible for contracts that delegate to address(0)), ownership would be permanently renounced. More practically, it wastes a transaction.

**Impact:** Negligible in practice.

**Recommended Fix:**
Add `require(newOwner != address(0))`.

---

### L-5: `setKeeper` Does Not Validate Against `address(0)`

**File:** `ILAlphaHook.sol`, line 438; `ILAlphaVault.sol`, line 417
**Severity:** LOW

**Description:**
Setting keeper to `address(0)` disables keeper functionality entirely (no EOA can match `address(0)`). While the owner can still call keeper functions (via `msg.sender != owner` fallback in `onlyKeeper`), this is a potential footgun.

**Impact:** Accidental keeper lock-out.

**Recommended Fix:**
Validate `_keeper != address(0)` or document this as intentional behavior.

---

### L-6: `claimFees` Transfers Without Checking Balance

**File:** `ILAlphaVault.sol`, lines 434-438
**Severity:** LOW

**Description:**
`claimFees` transfers `accumulatedFees` without verifying that the vault has sufficient balance. If fees were accumulated but the vault's balance is insufficient (e.g., due to the C-1 bug or LP losses), the transfer will revert. This is a graceful failure (revert, not loss), but it prevents partial fee claims.

**Impact:** Owner cannot claim fees if vault balance is insufficient, but no fund loss.

**Recommended Fix:**
Claim `min(accumulatedFees, asset.balanceOf(address(this)))`.

---

## INFORMATIONAL

### I-1: `ILAlphaVault.deposit` Does Not Override `mint()`

**File:** `ILAlphaVault.sol`
**Severity:** INFORMATIONAL

**Description:**
The vault overrides `deposit()` to add `whenNotPaused`, `nonReentrant`, `DepositTooSmall`, `DepositCapExceeded`, and `_checkTWAP()` guards. However, the ERC-4626 `mint()` function is not overridden and remains callable without any of these protections. A user can bypass the deposit cap, pause state, minimum deposit check, and TWAP check by calling `mint()` directly.

Similarly, `redeem()` is not overridden but `withdraw()` hooks into `beforeWithdraw` via the parent contract. Both `withdraw()` and `redeem()` call `beforeWithdraw` through solmate's ERC4626 base, so the withdrawal path is likely safe. But `mint()` bypasses all deposit-side protections.

**Recommended Fix:**
Override `mint()` with the same guards, or add guards to an `afterDeposit` hook that is called by both paths.

---

### I-2: Solidity ^0.8.26 Provides Built-in Overflow Protection

**File:** All files
**Severity:** INFORMATIONAL

**Description:**
All contracts use Solidity ^0.8.26, which provides automatic overflow/underflow checks. The explicit caps to `type(uint128).max` in the hook (lines 299, 313) are good defensive practice. No unchecked blocks are used.

**Status:** No action needed.

---

### I-3: `getVolEstimate` Annualization Is Simplified

**File:** `ILAlphaHook.sol`, lines 399-403
**Severity:** INFORMATIONAL

**Description:**
The annualized vol calculation `hourlyVar * 8760` is a simple scaling without square root. This represents annualized variance, not annualized volatility. The naming `annualizedVol` is misleading (should be `annualizedVar`).

**Impact:** Off-chain consumers may misinterpret the value.

**Recommended Fix:**
Rename to `annualizedVar` or apply `sqrt()` for true annualized vol.

---

### I-4: `HODLVault` Has No Owner or Admin Functions

**File:** `controls/HODLVault.sol`
**Severity:** INFORMATIONAL

**Description:**
The HODLVault has no owner, no pause mechanism, and no emergency withdrawal. Once deployed, it cannot be upgraded or paused. For a control vault this is acceptable, but any tokens accidentally sent to it (outside of ERC-4626 deposits) are permanently locked.

**Impact:** None for intended use.

---

### I-5: `ILAlphaHook` Storage Layout Not Upgrade-Safe

**File:** `ILAlphaHook.sol`
**Severity:** INFORMATIONAL

**Description:**
The hook contract does not use storage gaps or an upgradeable proxy pattern. If future upgrades are planned, the storage layout is not forward-compatible.

**Impact:** None if the contract is not intended to be upgradeable.

---

## Attack Scenario: Combined Exploitation (C-1 + H-1 + H-2)

An attacker could chain findings C-1, H-1, and H-2:

1. **Manipulate price** (H-1 bypass): Execute a swap to set both `lastTick` and `spotTick` to the same manipulated value, bypassing the `_checkTWAP()` guard.
2. **Trigger rebalance** (H-2): Call `rebalance()` to force the vault to add liquidity at the manipulated price, receiving unfavorable LP position.
3. **Reverse manipulation**: Swap back, causing IL on the vault's new position.
4. **Withdraw with fee** (C-1): Withdraw with inflated share price while the fee accounting corrupts the vault state.

**Estimated Impact:** Up to 100% of vault TVL depending on deposit cap and position size.

---

## Appendix: Files Reviewed

| File | Lines | Findings |
|------|-------|----------|
| `ILAlphaHook.sol` | 446 | H-4, M-3, M-4, M-5, L-4, L-5, I-3, I-5 |
| `ILAlphaVault.sol` | 448 | C-1, H-1, H-2, H-3, M-1, M-2, L-3, L-4, L-5, L-6, I-1 |
| `BaseVault.sol` | 53 | I-2 |
| `SwapHelper.sol` | 133 | M-6 |
| `AlwaysLPVault.sol` | 48 | L-1, L-2 |
| `HODLVault.sol` | 18 | I-4 |
