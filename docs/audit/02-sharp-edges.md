# Sharp Edges Analysis — IL Alpha Vault

**Methodology:** Trail of Bits "sharp edges" framework
**Date:** 2026-03-20
**Scope:** All 6 contracts in `contracts/src/`
**Auditor:** Claude Opus 4.6 (automated)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 3     |
| HIGH     | 7     |
| MEDIUM   | 8     |
| LOW      | 5     |

---

## CRITICAL

### SE-01: `setTwapThreshold` can be set to zero or negative — disables manipulation protection

- **Category:** Config Footgun
- **File:** `ILAlphaVault.sol:425-427`
- **Description:** `setTwapThreshold(int24 _threshold)` accepts any `int24` value including zero and negative values. Setting to zero means `deviation > 0` is the only check, which passes for identical ticks but blocks all deposits/withdrawals when there is *any* tick movement (effectively bricking the vault). Setting to a negative value means `deviation > negativeNumber` always passes (signed comparison), completely disabling the TWAP manipulation guard. There are no bounds checks whatsoever.
- **Impact:** Owner can accidentally disable sandwich/flashloan protection or brick deposits and withdrawals.
- **Fix:**
```solidity
function setTwapThreshold(int24 _threshold) external onlyOwner {
    require(_threshold >= 10 && _threshold <= 2000, "Threshold out of range");
    twapThreshold = _threshold;
}
```

### SE-02: Withdrawal fee is accounted but never deducted from transferred amount

- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:299-311`
- **Description:** `beforeWithdraw` calculates a fee and adds it to `accumulatedFees`, but never actually reduces the `assets` amount sent to the withdrawer. The ERC-4626 `withdraw()` flow in solmate transfers the full `assets` to the receiver *after* `beforeWithdraw` runs. The fee is phantom — it inflates `accumulatedFees` but the tokens are still sent. When `claimFees()` is called, it transfers tokens that may belong to depositors, draining the vault.
- **Impact:** Double-counting: depositor receives full amount AND fee is claimed separately. This drains vault assets, causing a loss for remaining depositors proportional to accumulated fees claimed.
- **Fix:** Override `withdraw`/`redeem` to deduct fees from the transferred amount, or implement fees at the share level (burn fewer shares than expected).

### SE-03: `setPoolKey` can change the pool while liquidity is deployed — stranded funds

- **Category:** Config Footgun
- **File:** `ILAlphaVault.sol:403-411`
- **Description:** The owner can call `setPoolKey()` while `deployedLiquidity > 0`. After the change, `_removeLiquidity()` will attempt to remove liquidity from the *new* pool (where the vault has none), while the actual liquidity remains stranded in the old pool. The `deployedLiquidity` counter becomes meaningless, and `totalAssets()` reads the wrong pool's price.
- **Impact:** Permanent loss of all deployed LP funds.
- **Fix:**
```solidity
function setPoolKey(PoolKey calldata _poolKey) external onlyOwner {
    require(deployedLiquidity == 0, "Must remove liquidity first");
    // ... existing validation ...
}
```

---

## HIGH

### SE-04: `_checkTWAP` uses hook's `lastTick` as TWAP proxy — trivially stale

- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:337-355`
- **Description:** The TWAP check compares the current spot tick against `volOracles[poolId].lastTick`, which is simply the tick at the time of the last swap processed by the hook. This is *not* a TWAP — it is a single historical data point. An attacker can: (1) execute a small swap to update `lastTick` to the manipulated price, (2) execute a large manipulation swap, (3) deposit/withdraw at the manipulated price. Since `lastTick` was just updated, the deviation is small and the check passes.
- **Impact:** The anti-manipulation guard is bypassable with a two-step attack.
- **Fix:** Implement a proper TWAP using Uniswap V4's oracle observations or a sliding window of tick samples.

### SE-05: `SwapHelper` uses raw `transferFrom` — no return value check

- **Category:** Token Issue
- **File:** `SwapHelper.sol:82, 89, 117, 124`
- **Description:** `ERC20(Currency.unwrap(c)).transferFrom(caller, address(poolManager), amt)` calls `transferFrom` directly on the ERC20 without using `SafeTransferLib`. Some tokens (notably USDT) do not return `bool` on `transfer`/`transferFrom`, causing the call to revert at the ABI decoding step on Solidity >=0.8. Other tokens return `false` instead of reverting on failure, which would be silently ignored.
- **Impact:** Swaps fail for non-standard tokens; silent failures possible for non-reverting tokens.
- **Fix:** Use `SafeTransferLib.safeTransferFrom()` from solmate (already imported in other contracts).

### SE-06: `setKeeper(address(0))` locks keeper-gated functions permanently

- **Category:** Missing Guardrail
- **File:** `ILAlphaHook.sol:438-439`, `ILAlphaVault.sol:417-419`
- **Description:** Both `setKeeper` functions accept `address(0)`. In `ILAlphaHook`, the `onlyKeeper` modifier allows `msg.sender == keeper || msg.sender == owner`, so the owner retains access. However, the keeper role is intended for automated bots — setting it to `address(0)` accidentally means only manual owner intervention works. There is no zero-address check or event emission on keeper change.
- **Impact:** Accidental operational disruption; no event for off-chain monitoring.
- **Fix:** Add `require(_keeper != address(0), "Zero address")` and emit a `KeeperUpdated` event.

### SE-07: `pushVolEstimate` allows 4x jump when `currentVar > 0` — comment says 2x

- **Category:** Design Misuse
- **File:** `ILAlphaHook.sol:359-377`
- **Description:** The comment says "max change per push is 2x current value" and "external estimate can't be more than 2x current on-chain var". But the code sets `maxExternal = currentVar * 4`. After blending 50/50: `(currentVar + 4*currentVar) / 2 = 2.5 * currentVar`. The actual max single-step change is 2.5x, not 2x. The code and comments are inconsistent, and the actual limit is more permissive than documented.
- **Impact:** Compromised keeper can manipulate vol oracle faster than expected.
- **Fix:** Set `maxExternal = currentVar * 3` for a true 2x blended max, or update docs to reflect the actual 2.5x limit.

### SE-08: `totalAssets()` sums token0 and token1 without price conversion

- **Category:** Math Issue
- **File:** `ILAlphaVault.sol:147-149`
- **Description:** `totalAssets()` returns `idle + lpValue0 + lpValue1`. The vault's `asset` is one specific token (e.g., USDC), but `lpValue0` and `lpValue1` are denominated in two different tokens with potentially very different prices and decimals. Summing raw amounts is only valid for 1:1 pegged same-decimal pairs. For any real pair (e.g., ETH/USDC), this produces a wildly incorrect total, breaking all share price calculations.
- **Impact:** Incorrect share pricing for non-pegged pairs. Depositors/withdrawers transact at wrong exchange rate. Exploitable for profit extraction.
- **Fix:** Convert the non-asset token amount to asset terms using the pool's current price (sqrtPriceX96) before summing.

### SE-09: `AlwaysLPVault.rebalance()` has no access control — anyone can inflate `deployedAssets`

- **Category:** Missing Guardrail
- **File:** `AlwaysLPVault.sol:33-40`
- **Description:** `rebalance()` is `external` with no modifier. Any caller can trigger it. While the function's logic is benign for this control vault (it just moves the idle balance counter to `deployedAssets`), the lack of any guard is inconsistent with the rest of the codebase and could mask integration issues in testing. More critically, `deployedAssets` is a pure accounting variable not backed by actual LP — the "deployed" assets are still in the contract's balance. `totalAssets()` double-counts them: `balanceOf(this) + deployedAssets` where `deployedAssets` was added from the same balance.
- **Impact:** `totalAssets()` is incorrect after `rebalance()` — the same tokens are counted twice. Share price inflates. New depositors get fewer shares than deserved. Existing holders can withdraw more than deposited.
- **Fix:** Actually transfer tokens to an LP position, or deduct from balance when adding to `deployedAssets`. For a control vault that merely simulates, subtract: `asset.safeTransfer(address(0xdead), idle)` or use a separate escrow.

### SE-10: No reentrancy guard on ILAlphaVault `withdraw`/`redeem`

- **Category:** Missing Guardrail
- **File:** `ILAlphaVault.sol` (inherited from `BaseVault`/`ERC4626`)
- **Description:** `deposit()` has `nonReentrant`, but `withdraw()` and `redeem()` (inherited from solmate's ERC4626) do not. The `beforeWithdraw` hook calls `_removeLiquidity()` which calls `poolManager.unlock()`, which invokes `unlockCallback()` — this crosses a trust boundary (PoolManager calls back into the vault). While PoolManager itself has reentrancy protection, the vault's own state (shares, `deployedLiquidity`) could be in an inconsistent intermediate state if any callback path reenters `withdraw`.
- **Impact:** Potential reentrancy during withdrawal via PoolManager callback path.
- **Fix:** Override `withdraw()` and `redeem()` with the `nonReentrant` modifier.

---

## MEDIUM

### SE-11: `setDepositCap(0)` bricks deposits with no warning

- **Category:** Config Footgun
- **File:** `ILAlphaVault.sol:421-423`
- **Description:** `setDepositCap(0)` is accepted. Since `totalAssets() + assets > 0` is always true for any nonzero deposit, all deposits are permanently blocked. While `setPaused(true)` exists for intentional pausing, an accidental `setDepositCap(0)` achieves the same effect less obviously, with no event or explicit semantic.
- **Fix:** Add `require(_cap >= VIRTUAL_ASSETS, "Cap too low")` or emit a dedicated event.

### SE-12: `_updateVolOracle` division by elapsed can amplify noise for small elapsed times

- **Category:** Math Issue
- **File:** `ILAlphaHook.sol:292`
- **Description:** `squaredReturn = (squaredReturn * 3600) / elapsed`. If `elapsed` is 1 second (consecutive blocks), the squared return is amplified by 3600x. A 1-tick change in 1 second is treated as equivalent to a 60-tick change in 1 hour. This makes the variance estimate extremely noisy for high-frequency swaps and biases it upward, causing the strategy to stay out of LP more than warranted.
- **Impact:** Systematic upward bias in volatility estimates reduces LP uptime and fee capture.
- **Fix:** Apply a minimum elapsed time floor (e.g., 60 seconds) or use a time-weighted accumulator instead of per-swap normalization.

### SE-13: Negative `int24` tick arithmetic in `afterInitialize` — rounding toward negative infinity not guaranteed

- **Category:** Math Issue
- **File:** `ILAlphaHook.sol:165-166`
- **Description:** `int24 lower = ((tick - halfRange) / spacing) * spacing`. In Solidity, integer division of negative numbers truncates toward zero (not toward negative infinity). For `tick = -1`, `spacing = 10`: `(-1 - 500) / 10 * 10 = -501 / 10 * 10 = -50 * 10 = -500`. This is actually correct for this case, but for values like `tick = -499`, `spacing = 60`: `(-999) / 60 * 60 = -16 * 60 = -960`, while the nearest aligned tick below is `-1020`. The lower tick will be above where expected, and the range is asymmetric around the current price.
- **Impact:** LP range may not be properly aligned with tick spacing, potentially placing ticks at invalid positions that `modifyLiquidity` will reject.
- **Fix:** Use floor division: `lower = tick - halfRange; lower = lower < 0 ? ((lower - spacing + 1) / spacing) * spacing : (lower / spacing) * spacing;`

### SE-14: `claimFees` does not verify contract has sufficient balance

- **Category:** Missing Guardrail
- **File:** `ILAlphaVault.sol:434-438`
- **Description:** `claimFees` transfers `accumulatedFees` worth of the asset token. But as noted in SE-02, fees are phantom — they were never actually withheld. If more fees have been "accumulated" than the vault holds in idle balance, the transfer will revert (for well-behaved ERC20s) or silently fail (for non-reverting tokens). Even if SE-02 is fixed, `claimFees` should verify balance.
- **Fix:** Add `require(asset.balanceOf(address(this)) >= fees, "Insufficient balance")` or `fees = min(fees, asset.balanceOf(address(this)))`.

### SE-15: `emergencyWithdraw` does not reset `accumulatedFees`

- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:441-447`
- **Description:** After emergency withdrawal, all LP is pulled and the vault is paused. But `accumulatedFees` retains its pre-emergency value. If the vault is later unpaused, `claimFees()` may drain tokens that depositors are entitled to.
- **Fix:** Reset `accumulatedFees = 0` in `emergencyWithdraw`.

### SE-16: No slippage protection on `_executeAddLiquidity` — 50/50 split is naive

- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:233-235`
- **Description:** Assets are split exactly 50/50 (`assets / 2` for each token), but the vault only holds the `asset` token. The code passes `amount0` and `amount1` to `getLiquidityForAmounts`, but the vault may not actually have `amount1` worth of the other token. When `_settleCurrency` tries to transfer the non-asset token, it will either revert (if balance is zero) or transfer tokens the vault does not own.
- **Impact:** `_executeAddLiquidity` will revert for any pool where the vault doesn't hold both tokens. LP provisioning is broken unless someone externally sends the second token.
- **Fix:** Implement a swap to acquire the second token before adding liquidity (using the pool itself or an external DEX), or only add single-sided liquidity.

### SE-17: `transferOwnership(address(0))` allows ownership renunciation via two-step

- **Category:** Missing Guardrail
- **File:** `ILAlphaHook.sol:426-429`, `ILAlphaVault.sol:391-394`
- **Description:** `transferOwnership(address(0))` sets `pendingOwner = address(0)`. While `acceptOwnership` requires `msg.sender == pendingOwner`, and no one can send from address(0), the pending state is stuck — `pendingOwner` is permanently set to zero, and the current owner cannot call `transferOwnership` again to fix it. Actually, re-reading: the owner *can* call `transferOwnership` again with a valid address since they retain ownership. So this is LOW impact. However, there is no check preventing `address(0)` which wastes a transaction.
- **Fix:** Add `require(newOwner != address(0))`.

### SE-18: `SwapHelper` stores state in storage slots between `swap()`/`unlock()` — front-runnable

- **Category:** Dangerous API
- **File:** `SwapHelper.sol:19-22, 33-42`
- **Description:** `swap()` writes `_pendingKey`, `_pendingZeroForOne`, `_pendingAmount`, `_isSwap` to storage, then calls `poolManager.unlock()`. If the PoolManager's unlock mechanism allows reentrant calls or if there is a MEV opportunity between the storage writes and the callback, the stored parameters could be observed and front-run. More practically, these storage slots are never cleared after use, leaving stale data that could cause confusion in debugging or unexpected behavior if the callback path changes.
- **Fix:** Clear `_pending*` state at the end of `unlockCallback`. Consider using transient storage (`TSTORE`/`TLOAD`) on Cancun+ chains.

---

## LOW

### SE-19: `setLPRange` does not validate tick alignment with pool's tickSpacing

- **Category:** Missing Guardrail
- **File:** `ILAlphaHook.sol:390-395`
- **Description:** `setLPRange` only checks `tickLower < tickUpper`. It does not verify that the ticks are multiples of the pool's `tickSpacing`. Misaligned ticks will cause `modifyLiquidity` to revert when the vault tries to add liquidity.
- **Fix:** Accept `PoolKey` as parameter and validate `tickLower % key.tickSpacing == 0 && tickUpper % key.tickSpacing == 0`.

### SE-20: `getVolEstimate` annualization is naive — multiplies hourly variance by 8760

- **Category:** Math Issue
- **File:** `ILAlphaHook.sol:402`
- **Description:** `annualizedVol = uint256(hourlyVar) * 8760`. This annualizes *variance* (sigma^2), not *volatility* (sigma). Annualized volatility should be `sqrt(hourlyVar * 8760)`. The returned `annualizedVol` is actually annualized variance, but the function name says "Vol". This is a view function so it does not affect on-chain logic, but off-chain consumers relying on it will get incorrect risk metrics.
- **Fix:** Rename to `annualizedVariance` or compute `sqrt(hourlyVar * 8760)` using a math library.

### SE-21: `HODLVault` has no access controls — anyone can deposit/withdraw

- **Category:** Missing Guardrail
- **File:** `HODLVault.sol:10-18`
- **Description:** The HODLVault has no owner, no pause mechanism, and no deposit cap. As a control/benchmark vault this is likely intentional, but it means anyone can use it as an unregulated ERC-4626 wrapper.
- **Impact:** Low — by design for benchmarking.
- **Fix:** Document the intentional lack of controls, or add them for consistency.

### SE-22: `AlwaysLPVault.beforeWithdraw` sets `deployedAssets = 0` on any shortfall

- **Category:** Design Misuse
- **File:** `AlwaysLPVault.sol:42-47`
- **Description:** When `idle < assets`, the entire `deployedAssets` is zeroed out regardless of how much was actually needed. This means a small withdrawal that slightly exceeds idle balance will wipe the full deployed tracking, causing `totalAssets()` to drop to just `balanceOf(this)`. Combined with SE-09's double-counting issue, this creates volatile share price swings.
- **Fix:** Reduce `deployedAssets` by only the deficit amount: `deployedAssets -= (assets - idle)`.

### SE-23: `COOLDOWN_SECONDS` is typed `uint24` — max ~4.6 hours, but set to 86400

- **Category:** Dangerous API
- **File:** `ILAlphaHook.sol:78`
- **Description:** `uint24 public constant COOLDOWN_SECONDS = 24 hours;` — `24 hours = 86400`. `uint24` max is `16777215`, so 86400 fits. This is not a bug, but using `uint24` for a time constant is unusual and error-prone for future modifications. If someone changes it to a larger value, `uint24` overflow would silently truncate at compile time (Solidity constant overflow is a compile error in 0.8+, so this is actually safe). Severity is low.
- **Fix:** Use `uint32` or `uint256` for time constants for clarity.

---

## Cross-Cutting Concerns

### No Timelock on Critical Admin Functions

All owner-only setters (`setPoolKey`, `setDepositCap`, `setTwapThreshold`, `setLPRange`, `setLambda`, `setPaused`) take effect immediately. A compromised owner key can:
- Set `twapThreshold` to `type(int24).max` (disable manipulation check)
- Set `depositCap` to `type(uint256).max` (remove cap)
- Change `poolKey` while liquidity is deployed (strand funds)
- Set `lambda` to extremes (bias vol oracle)

**Recommendation:** Implement a timelock (24-48h) for non-emergency admin actions, or use a multisig.

### Fee-on-Transfer and Rebasing Token Incompatibility

The vault uses `safeTransfer` for the asset token and relies on `balanceOf(address(this))` for idle accounting. Fee-on-transfer tokens would cause `totalAssets()` to overstate balances (the received amount is less than the transferred amount). Rebasing tokens would cause balances to change without corresponding share adjustments. Neither case is handled.

**Recommendation:** Document that fee-on-transfer and rebasing tokens are unsupported, or add pre/post balance checks on deposits.

### Solmate ERC4626 `withdraw` Burns Shares Before Transfer

Solmate's `withdraw` calls `beforeWithdraw`, then `_burn`, then `asset.safeTransfer`. The `_burn` happens before the external call, which is correct for CEI (checks-effects-interactions). However, `beforeWithdraw` calls `_removeLiquidity` which makes external calls (to PoolManager) *before* shares are burned. This ordering means an attacker could potentially exploit the callback to observe stale share balances.

**Recommendation:** Verify that the PoolManager callback cannot reenter the vault's share-related functions.

---

*End of sharp edges analysis.*
