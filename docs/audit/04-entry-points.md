# 04 - Entry Point Analysis

Trail of Bits-style entry point enumeration for all state-changing externally callable functions across the IL Alpha Vault protocol.

**Scope:** 6 contracts in `contracts/src/`

**Access Level Key:**
- **PUBLIC** -- callable by anyone, no access control
- **KEEPER** -- restricted to `keeper` address or `owner`
- **OWNER** -- restricted to `owner` address only
- **POOL_MANAGER** -- restricted to Uniswap V4 PoolManager contract only
- **PENDING_OWNER** -- restricted to `pendingOwner` address only

---

## 1. ILAlphaHook.sol

Core volatility oracle and LP toggle hook. Receives callbacks from Uniswap V4 PoolManager.

| Function | Access | State Changes | External Calls | Value Flow | Risk |
|----------|--------|---------------|----------------|------------|------|
| `afterInitialize()` | POOL_MANAGER | `poolStates[poolId]` (full init), `volOracles[poolId]` (full init) | `poolManager.getSlot0()` (implicit via StateLibrary, but only in afterSwap) | None | LOW -- only called once per pool init by PoolManager |
| `afterSwap()` | POOL_MANAGER | `volOracles[poolId].ewmaVar`, `.lastTick`, `.lastTimestamp`; `poolStates[poolId].ewmaVolume`, `.isLPActive`, `.lastToggleTime` | `poolManager.getSlot0()` | None | MEDIUM -- manipulated swap sizes can influence EWMA volume and trigger LP toggle; volume spike detection bypasses cooldown |
| `pushVolEstimate()` | KEEPER | `volOracles[poolId].ewmaVar`, `.lastTimestamp` | None | None | HIGH -- compromised keeper can skew vol oracle up to 4x current value per call; repeated calls can drift vol arbitrarily |
| `triggerEvaluation()` | KEEPER | `poolStates[poolId].isLPActive`, `.lastToggleTime` | None | None | MEDIUM -- forces LP toggle evaluation outside of swaps; bounded by cooldown |
| `setLPRange()` | OWNER | `poolStates[poolId].tickLower`, `.tickUpper` | None | None | MEDIUM -- changing range while LP is active could cause vault to operate on stale range until next rebalance |
| `transferOwnership()` | OWNER | `pendingOwner` | None | None | LOW -- two-step pattern, no immediate effect |
| `acceptOwnership()` | PENDING_OWNER | `owner`, `pendingOwner` | None | None | LOW -- completes ownership transfer |
| `setKeeper()` | OWNER | `keeper` | None | None | LOW -- admin function |
| `setLambda()` | OWNER | `volOracles[poolId].lambda` | None | None | MEDIUM -- lambda affects EWMA decay rate; extreme values (even within 5000-9900 range) can make oracle sluggish or hyper-reactive |

---

## 2. ILAlphaVault.sol

Main ERC-4626 vault. Manages user deposits/withdrawals and LP position in Uniswap V4.

| Function | Access | State Changes | External Calls | Value Flow | Risk |
|----------|--------|---------------|----------------|------------|------|
| `deposit()` | PUBLIC | `totalSupply` (mint shares), `balanceOf[receiver]`, `_locked` | `asset.safeTransferFrom()`, `hook.isLPActive()` (via `_checkTWAP`), `poolManager.getSlot0()`, `hook.volOracles()` | Tokens IN: depositor -> vault | HIGH -- public entry, TWAP check uses hook's lastTick as proxy (not true TWAP); deposit cap enforced but checked against manipulable `totalAssets()` |
| `mint()` | PUBLIC | `totalSupply`, `balanceOf[receiver]` | `asset.safeTransferFrom()` | Tokens IN: depositor -> vault | HIGH -- inherited from solmate ERC4626, NOT overridden, so it BYPASSES `whenNotPaused`, `nonReentrant`, deposit cap check, `_checkTWAP`, and minimum deposit check |
| `withdraw()` | PUBLIC | `totalSupply` (burn shares), `balanceOf[owner]`, `allowance`, `accumulatedFees`, `deployedLiquidity`, `_locked`, `_pendingAction` | `asset.safeTransfer()`, `poolManager.unlock()`, `poolManager.modifyLiquidity()`, `poolManager.take()`, `hook.getPoolStrategy()`, `hook.volOracles()`, `poolManager.getSlot0()` | Tokens OUT: vault -> receiver; may remove LP from pool | CRITICAL -- triggers LP removal if idle < requested; withdrawal fee accounting but fee not deducted from transferred amount; TWAP check on withdrawal |
| `redeem()` | PUBLIC | Same as `withdraw()` | Same as `withdraw()` | Tokens OUT: vault -> receiver | CRITICAL -- same risks as withdraw; inherited from solmate, calls `beforeWithdraw` hook |
| `rebalance()` | PUBLIC | `deployedLiquidity`, `_locked`, `_pendingAction` | `hook.isLPActive()`, `poolManager.unlock()`, `poolManager.modifyLiquidity()`, `poolManager.sync()`, `poolManager.settle()`, `poolManager.take()`, `asset.safeTransfer()`, `hook.getPoolStrategy()` | Tokens flow between vault and PoolManager | HIGH -- anyone can trigger; adds/removes LP based on hook signal; no slippage protection on LP add/remove |
| `unlockCallback()` | POOL_MANAGER | `deployedLiquidity` | `poolManager.modifyLiquidity()`, `poolManager.sync()`, `poolManager.settle()`, `poolManager.take()`, `asset.safeTransfer()`, `hook.getPoolStrategy()` | Tokens flow between vault and PoolManager | MEDIUM -- only callable by PoolManager during unlock; relies on `_pendingAction` state |
| `transferOwnership()` | OWNER | `pendingOwner` | None | None | LOW |
| `acceptOwnership()` | PENDING_OWNER | `owner`, `pendingOwner` | None | None | LOW |
| `setPoolKey()` | OWNER | `poolKey` | None | None | MEDIUM -- validates asset is in pool pair but changing poolKey while LP is deployed is dangerous |
| `setPaused()` | OWNER | `paused` | None | None | LOW |
| `setKeeper()` | OWNER | `keeper` | None | None | LOW |
| `setDepositCap()` | OWNER | `depositCap` | None | None | LOW |
| `setTwapThreshold()` | OWNER | `twapThreshold` | None | None | MEDIUM -- setting threshold too high disables manipulation protection; setting to 0 blocks all deposits/withdrawals when LP is active |
| `setWithdrawalFeeBps()` | OWNER | `withdrawalFeeBps` | None | None | LOW -- capped at 100 bps (1%) |
| `claimFees()` | OWNER | `accumulatedFees` | `asset.safeTransfer()` | Tokens OUT: vault -> `to` | MEDIUM -- transfers accumulated fees; no validation that `to` is non-zero |
| `emergencyWithdraw()` | OWNER | `deployedLiquidity`, `paused`, `_locked`, `_pendingAction` | `poolManager.unlock()`, `poolManager.modifyLiquidity()`, `poolManager.take()`, `hook.getPoolStrategy()` | Tokens IN: pool -> vault (LP removed) | MEDIUM -- removes all LP and pauses; no slippage protection |

### Inherited ERC20 State-Changing Functions (from solmate)

| Function | Access | State Changes | External Calls | Value Flow | Risk |
|----------|--------|---------------|----------------|------------|------|
| `transfer()` | PUBLIC | `balanceOf[msg.sender]`, `balanceOf[to]` | None | Share tokens transferred | LOW |
| `transferFrom()` | PUBLIC | `balanceOf[from]`, `balanceOf[to]`, `allowance` | None | Share tokens transferred | LOW |
| `approve()` | PUBLIC | `allowance[msg.sender][spender]` | None | None | LOW |
| `permit()` | PUBLIC | `allowance[owner][spender]`, `nonces[owner]` | None | None | LOW |

---

## 3. BaseVault.sol

Abstract contract. No additional externally callable state-changing functions beyond what is inherited from solmate's ERC4626/ERC20 (covered above). All functions are `view` overrides.

---

## 4. SwapHelper.sol

Testnet helper for keeper bot. Executes swaps and adds liquidity.

| Function | Access | State Changes | External Calls | Value Flow | Risk |
|----------|--------|---------------|----------------|------------|------|
| `swap()` | OWNER | `_pendingKey`, `_pendingZeroForOne`, `_pendingAmount`, `_isSwap` | `poolManager.unlock()` -> triggers `unlockCallback` | Tokens flow: caller <-> PoolManager (via `transferFrom`) | MEDIUM -- owner-only; uses caller's token approvals; no slippage protection (uses MIN/MAX sqrt price limits) |
| `addLiquidity()` | OWNER | `_pendingKey`, `_pendingAmount`, `_isSwap` | `poolManager.unlock()` -> triggers `unlockCallback` | Tokens flow: caller <-> PoolManager (via `transferFrom`) | LOW -- owner-only; hardcoded full-range ticks |
| `unlockCallback()` | POOL_MANAGER | None (reads pending state) | `poolManager.swap()` or `poolManager.modifyLiquidity()`, `poolManager.sync()`, `poolManager.settle()`, `poolManager.take()`, `ERC20.transferFrom()` | Tokens flow: caller <-> PoolManager | MEDIUM -- no reentrancy guard; pending state could theoretically be manipulated if unlock is called unexpectedly |

---

## 5. AlwaysLPVault.sol (controls/)

Benchmark control vault. Always LPs.

| Function | Access | State Changes | External Calls | Value Flow | Risk |
|----------|--------|---------------|----------------|------------|------|
| `deposit()` | PUBLIC | `totalSupply`, `balanceOf[receiver]` | `asset.safeTransferFrom()` | Tokens IN | LOW -- inherited, no overrides |
| `mint()` | PUBLIC | `totalSupply`, `balanceOf[receiver]` | `asset.safeTransferFrom()` | Tokens IN | LOW -- inherited |
| `withdraw()` | PUBLIC | `totalSupply`, `balanceOf[owner]`, `allowance`, `deployedAssets` | `asset.safeTransfer()` | Tokens OUT | MEDIUM -- `beforeWithdraw` zeroes `deployedAssets` but tokens aren't actually in a pool; phantom accounting |
| `redeem()` | PUBLIC | Same as `withdraw()` | `asset.safeTransfer()` | Tokens OUT | MEDIUM -- same issue |
| `rebalance()` | PUBLIC | `deployedAssets` | None | None (accounting only) | MEDIUM -- anyone can call; adds idle balance to `deployedAssets` but no actual LP deployment; `deployedAssets` is phantom accounting that inflates `totalAssets()` |
| `transfer()` | PUBLIC | `balanceOf` | None | Share tokens | LOW |
| `transferFrom()` | PUBLIC | `balanceOf`, `allowance` | None | Share tokens | LOW |
| `approve()` | PUBLIC | `allowance` | None | None | LOW |
| `permit()` | PUBLIC | `allowance`, `nonces` | None | None | LOW |

---

## 6. HODLVault.sol (controls/)

Benchmark control vault. Hold only, never LPs. No additional state-changing functions beyond inherited ERC4626/ERC20.

| Function | Access | State Changes | External Calls | Value Flow | Risk |
|----------|--------|---------------|----------------|------------|------|
| `deposit()` | PUBLIC | `totalSupply`, `balanceOf[receiver]` | `asset.safeTransferFrom()` | Tokens IN | LOW |
| `mint()` | PUBLIC | `totalSupply`, `balanceOf[receiver]` | `asset.safeTransferFrom()` | Tokens IN | LOW |
| `withdraw()` | PUBLIC | `totalSupply`, `balanceOf[owner]`, `allowance` | `asset.safeTransfer()` | Tokens OUT | LOW |
| `redeem()` | PUBLIC | `totalSupply`, `balanceOf[owner]`, `allowance` | `asset.safeTransfer()` | Tokens OUT | LOW |
| `transfer()` | PUBLIC | `balanceOf` | None | Share tokens | LOW |
| `transferFrom()` | PUBLIC | `balanceOf`, `allowance` | None | Share tokens | LOW |
| `approve()` | PUBLIC | `allowance` | None | None | LOW |
| `permit()` | PUBLIC | `allowance`, `nonces` | None | None | LOW |

---

## Top 5 Highest-Risk Entry Points

### 1. `ILAlphaVault.mint()` -- CRITICAL (Access Control Bypass)

**File:** `contracts/src/ILAlphaVault.sol` (inherited from solmate ERC4626, not overridden)

The `deposit()` function is overridden with `whenNotPaused`, `nonReentrant`, deposit cap enforcement, minimum deposit check, and TWAP manipulation check. However, `mint()` is **not overridden** and inherits the base solmate implementation directly. This means:
- Deposits can be made **while the vault is paused**
- Deposits can be made **exceeding the deposit cap**
- Deposits can be made **during price manipulation** (no TWAP check)
- Deposits can be made **with arbitrarily small amounts** (no minimum)
- The reentrancy guard is bypassed

This is the highest-severity finding: all protective invariants on the deposit path are bypassable via `mint()`.

### 2. `ILAlphaVault.withdraw()` / `redeem()` -- HIGH (Withdrawal Fee Not Deducted)

**File:** `contracts/src/ILAlphaVault.sol`, line 299-312

The `beforeWithdraw` hook increments `accumulatedFees` based on `withdrawalFeeBps`, but the fee is **never subtracted from the `assets` amount** actually transferred to the user. The solmate `withdraw()` function transfers the full `assets` amount to the receiver after `beforeWithdraw` runs. This means:
- The vault tracks fees in `accumulatedFees` but never actually retains them
- `claimFees()` will attempt to transfer tokens that were already sent to withdrawers
- Over time, `accumulatedFees` becomes a phantom balance, and `claimFees()` will either revert or drain other depositors' funds

### 3. `ILAlphaVault.rebalance()` -- HIGH (Public + No Slippage Protection)

**File:** `contracts/src/ILAlphaVault.sol`, line 176

Anyone can call `rebalance()`. The function adds/removes liquidity with **no slippage bounds** -- it accepts whatever the pool gives. Combined with being publicly callable:
- An attacker can sandwich the `rebalance()` call: manipulate price -> trigger rebalance (which adds LP at bad price) -> reverse manipulation
- The 50/50 asset split for two-sided LP (line 234-235) is a simplification that leaks value when the pool price is not centered in the tick range
- LP removal also has no minimum output check

### 4. `ILAlphaHook.pushVolEstimate()` -- HIGH (Oracle Manipulation via Keeper)

**File:** `contracts/src/ILAlphaHook.sol`, line 359

A compromised keeper key can manipulate the volatility oracle:
- Rate limit allows up to 4x the current value per call (line 366), not 2x as the comment states
- When `currentVar == 0`, the cap is `type(uint128).max` -- effectively unlimited
- Repeated calls can ratchet the oracle to any value: push high -> new EWMA is high -> push 4x of new high -> repeat
- This directly controls whether LP is active or inactive, enabling forced LP deployment into adverse conditions or forced withdrawal

### 5. `ILAlphaHook.afterSwap()` -- MEDIUM-HIGH (Volume Spike Bypass of Cooldown)

**File:** `contracts/src/ILAlphaHook.sol`, line 220

The afterSwap hook updates the vol oracle and can toggle LP state. Key risks:
- Volume spike detection (line 241) bypasses the 24-hour cooldown, allowing an attacker to force LP deactivation by executing a single large swap (>3x EWMA volume)
- The EWMA volume is updated **after** the spike check (line 244), so the spike threshold is based on pre-swap EWMA -- but the new EWMA incorporates the spike, raising the bar for future spike detection
- An attacker with sufficient capital can repeatedly trigger spike -> wait for EWMA to decay -> spike again, keeping LP permanently disabled
- The `elapsed == 0` check in `_updateVolOracle` (line 283) means same-block swaps skip vol updates, allowing MEV bots to execute swaps without affecting the oracle

---

## Summary Statistics

| Contract | Total State-Changing Entry Points | PUBLIC | KEEPER | OWNER | POOL_MANAGER |
|----------|----------------------------------|--------|--------|-------|--------------|
| ILAlphaHook | 9 | 0 | 2 | 4 | 2 (+1 pending_owner) |
| ILAlphaVault | 17 | 8 (incl. inherited ERC20/4626) | 0 | 8 | 1 (+1 pending_owner) |
| BaseVault | 0 (abstract) | -- | -- | -- | -- |
| SwapHelper | 3 | 0 | 0 | 2 | 1 |
| AlwaysLPVault | 9 | 8 (incl. inherited) | 0 | 0 | 0 |
| HODLVault | 8 | 8 (incl. inherited) | 0 | 0 | 0 |

**Total unique state-changing entry points across protocol: 46**

### Critical Action Items

1. **Override `mint()` in ILAlphaVault** with the same guards as `deposit()` -- this is a must-fix before any deployment.
2. **Fix withdrawal fee accounting** -- either deduct fee from transferred amount or use a different fee mechanism.
3. **Add slippage protection to `rebalance()`** -- minimum output amounts for LP add/remove operations.
4. **Fix `pushVolEstimate()` rate limit** -- comment says 2x but code allows 4x; consider tighter bounds and per-block rate limiting.
5. **Review cooldown bypass** in volume spike path -- consider whether emergency LP-off should have its own separate cooldown or require keeper confirmation.
