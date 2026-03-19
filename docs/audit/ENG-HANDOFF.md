# Security Audit Handoff — Engineering

**Date:** 2026-03-20
**Audited by:** Trail of Bits methodology (8-phase automated audit)
**Full reports:** `docs/audit/00-SUMMARY.md` + 8 detailed reports

---

## TL;DR

4 critical, 8 high severity bugs found. **Do not deploy with real funds until C-1 through C-4 are fixed.** Total fix effort: ~4 hours for all critical+high.

---

## CRITICAL — Fix Immediately (4 items, ~50 min)

### C-1: Withdrawal fee is phantom — never actually deducted
**File:** `ILAlphaVault.sol:299-306`

`beforeWithdraw()` increments `accumulatedFees` but solmate's `withdraw()`/`redeem()` still transfers the full `assets` amount to the user. The fee exists only in accounting. When owner calls `claimFees()`, it drains tokens belonging to other depositors.

**Fix:** Override `withdraw()` and `redeem()` to deduct fee from the transferred amount:
```solidity
function withdraw(uint256 assets, address receiver, address owner_)
    public override nonReentrant whenNotPaused returns (uint256 shares)
{
    _checkTWAP();
    uint256 fee = (assets * withdrawalFeeBps) / 10_000;
    // Transfer (assets - fee) to user, keep fee in vault
    shares = super.withdraw(assets, receiver, owner_);
    // Or: restructure so beforeWithdraw reduces the effective transfer
}
```
The current `beforeWithdraw` approach won't work because solmate calls `asset.safeTransfer(receiver, assets)` AFTER `beforeWithdraw` — so you can't reduce the amount from inside the hook. You need to override the full `withdraw`/`redeem` functions.

---

### C-2: `mint()` bypasses all deposit guards
**File:** `ILAlphaVault.sol` (missing override)

`deposit()` has `whenNotPaused`, `nonReentrant`, `DepositTooSmall`, `DepositCapExceeded`, `_checkTWAP()`. But `mint()` is inherited from solmate with zero guards. Anyone can call `mint()` to bypass pause, cap, TWAP check, and reentrancy protection.

**Fix:**
```solidity
function mint(uint256 shares, address receiver)
    public override whenNotPaused nonReentrant returns (uint256 assets)
{
    assets = previewMint(shares);
    if (assets < VIRTUAL_ASSETS) revert DepositTooSmall();
    if (totalAssets() + assets > depositCap) revert DepositCapExceeded();
    _checkTWAP();
    assets = super.mint(shares, receiver);
}
```

---

### C-3: `setPoolKey()` can strand active liquidity
**File:** `ILAlphaVault.sol:403-411`

If `deployedLiquidity > 0` and owner calls `setPoolKey()`, the LP position in the old pool becomes permanently unreachable. No way to recover funds.

**Fix:**
```solidity
function setPoolKey(PoolKey calldata _poolKey) external onlyOwner {
    require(deployedLiquidity == 0, "Remove LP first");
    // ... existing validation
}
```

---

### C-4: `setTwapThreshold()` has no bounds
**File:** `ILAlphaVault.sol:425-427`

Setting to 0 → every deposit/withdraw reverts (vault bricked). Setting to `type(int24).max` → manipulation protection disabled.

**Fix:**
```solidity
function setTwapThreshold(int24 _threshold) external onlyOwner {
    require(_threshold >= 10 && _threshold <= 2000, "Threshold out of range");
    twapThreshold = _threshold;
}
```

---

## HIGH — Fix Before Testnet With Real Users (8 items, ~3 hours)

### H-1: TWAP check is not actually TWAP
**File:** `ILAlphaVault.sol:337-355`

`_checkTWAP()` compares spot tick vs hook's `lastTick`. That's just the tick from the most recent swap — not a time-weighted average. An attacker can manipulate both in the same block.

**Fix:** Implement a tick accumulator (sliding window of N observations) in the hook, or integrate an external oracle. This is the biggest refactor.

### H-2: `rebalance()` has no slippage protection
**File:** `ILAlphaVault.sol:224-265, 275-295`

`modifyLiquidity()` is called without min amount checks. MEV bots can sandwich every rebalance.

**Fix:** Add `minAmount0`/`minAmount1` parameters and revert if actual amounts deviate beyond tolerance.

### H-3: Vault holds one token but provides two-sided LP
**File:** `ILAlphaVault.sol:233-235`

`assets / 2` split assumes vault has both tokens. In reality, vault only holds the `asset` token. The second token needs to be acquired via swap first, or LP should be single-sided.

**Fix:** Either implement a pre-swap to acquire token1, or use single-sided liquidity provision.

### H-4: `pushVolEstimate` rate limit is 4x, not 2x
**File:** `ILAlphaHook.sol:366`

NatSpec says "max change per push is 2x" but `maxExternal = currentVar * 4`. Also, when `currentVar == 0`, limit is `type(uint128).max`.

**Fix:** Change to `currentVar * 2` (or `* 3` for effective 2x after blending). Add a cap when `currentVar == 0` (e.g., `1e18`).

### H-5: `withdraw()`/`redeem()` lack reentrancy guard
**File:** `ILAlphaVault.sol`

`deposit()` and `rebalance()` have `nonReentrant`. `withdraw()`/`redeem()` don't, but they trigger `_removeLiquidity()` → `poolManager.unlock()` → external callback chain.

**Fix:** Override both with `nonReentrant`.

### H-6: AlwaysLPVault double-counts assets
**File:** `AlwaysLPVault.sol:33-39`

`rebalance()` adds to `deployedAssets` but tokens stay in the contract. `totalAssets() = balance + deployedAssets` double-counts.

**Fix:** Transfer tokens out or track properly. Since this is a control/benchmark vault, consider documenting the limitation or removing the simulated deployment.

### H-7: `totalAssets()` sums different tokens without conversion
**File:** `ILAlphaVault.sol:149`

`idle + lpValue0 + lpValue1` adds USDC balance + token0 LP value + token1 LP value as if they're the same denomination.

**Fix:** Use an oracle or compute value in terms of the vault's asset token only.

### H-8: Admin setters emit no events
**Files:** `ILAlphaVault.sol`, `ILAlphaHook.sol`

`setKeeper`, `setLambda`, `setPoolKey`, `setPaused`, `setDepositCap`, `setTwapThreshold`, `setWithdrawalFeeBps` — all silent. Makes monitoring and incident response impossible.

**Fix:** Add events to every admin setter.

---

## How To Verify Fixes

All 8 detailed reports are in `docs/audit/`. Report 03 (`03-property-based-testing.md`) includes 7 ready-to-use Foundry fuzz test functions — add them to validate fixes.

After fixing, run:
```bash
cd contracts && forge test -vvv
```

Key new tests to add:
1. `test_mint_respects_pause()` — verify `mint()` reverts when paused
2. `test_withdrawal_fee_actually_deducted()` — verify user receives `assets - fee`
3. `test_setPoolKey_reverts_with_active_lp()` — verify guard works
4. `test_twapThreshold_bounds()` — verify 0 and extreme values revert

---

## Questions?

Full audit reports: `docs/audit/01-*.md` through `docs/audit/08-*.md`
Summary with all 38 findings: `docs/audit/00-SUMMARY.md`
