# Spec-to-Code Compliance Report

**Audit Type:** Trail of Bits-style specification compliance verification
**Date:** 2026-03-20
**Scope:** All contracts in `contracts/src/`, verified against NatSpec, CLAUDE.md, ROADMAP.md, COMPETITIVE.md

---

## Summary

| Category | Compliant | Non-Compliant | Partial | Missing |
|----------|-----------|---------------|---------|---------|
| NatSpec vs Implementation | 11 | 2 | 2 | 0 |
| ERC-4626 Compliance | 7 | 2 | 1 | 0 |
| Uniswap V4 Hook Interface | 8 | 0 | 0 | 0 |
| Mathematical Claims | 3 | 1 | 1 | 0 |
| Stated Security Properties | 2 | 1 | 2 | 0 |
| Missing Implementations | 0 | 0 | 0 | 4 |

**Critical findings: 3 | High: 3 | Medium: 4 | Low: 4 | Informational: 3**

---

## 1. NatSpec vs Implementation

### 1.1 ILAlphaHook: "EWMA vol oracle to decide whether LP is +EV"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:14` — `@notice Uniswap V4 hook that uses EWMA vol oracle to decide whether LP is +EV`
- **Code reference:** `ILAlphaHook.sol:342-352` — `_evaluateLPToggle` compares `feeYield > ilCost`
- **Assessment:** The hook does compute EWMA variance and compare fee yield vs IL cost. The toggle logic matches the stated spec.

### 1.2 ILAlphaHook: "only provide liquidity when fee yield > IL cost"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:16-17`
- **Code reference:** `ILAlphaHook.sol:345` — `bool shouldBeActive = feeYield > ilCost`
- **Assessment:** Direct boolean comparison. Toggle is set accordingly.

### 1.3 ILAlphaHook: "keeper can also push external vol estimates for accuracy"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:31-32`
- **Code reference:** `ILAlphaHook.sol:359-377` — `pushVolEstimate` function
- **Assessment:** Implemented with rate limiting and 50/50 blending.

### 1.4 ILAlphaHook: VolOracle struct "packed into 1 storage slot (208 bits)"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:57` — `@dev Layout: ewmaVar(128) + lastTick(24) + lastTimestamp(40) + lambda(16) = 208 bits`
- **Code reference:** `ILAlphaHook.sol:58-63`
- **Assessment:** 128 + 24 + 40 + 16 = 208 bits. Fits in one 256-bit slot. Packing is correct.

### 1.5 ILAlphaHook: "Rate limited: max change per push is 2x current value"

- **Status:** NON-COMPLIANT
- **Severity:** Critical
- **Spec reference:** `ILAlphaHook.sol:357` — `@dev Rate limited: max change per push is 2x current value`
- **Code reference:** `ILAlphaHook.sol:366` — `uint256 maxExternal = currentVar == 0 ? type(uint128).max : currentVar * 4`
- **Gap description:** The NatSpec comment says "max change per push is 2x current value" but the code uses `currentVar * 4` as the cap. After 50/50 blending with the current value (`(currentVar + externalVar) / 2`), if `externalVar = currentVar * 4`, the blended result is `(currentVar + 4 * currentVar) / 2 = 2.5 * currentVar`. This means the effective max change is 2.5x, not 2x. To achieve a true 2x cap on the blended result, `maxExternal` should be `currentVar * 3` (yielding `(currentVar + 3 * currentVar) / 2 = 2 * currentVar`).
- **Risk assessment:** A compromised keeper can push vol 2.5x per call instead of the documented 2x. Over multiple calls, this compounds — the keeper can ramp vol exponentially. The NatSpec gives auditors and integrators a false sense of tighter protection. This is a spec-to-code mismatch that could be exploited for vol oracle manipulation.

### 1.6 ILAlphaHook: "log_return approx (currentTick - lastTick) * ln(1.0001)"

- **Status:** PARTIAL
- **Spec reference:** `ILAlphaHook.sol:279`
- **Code reference:** `ILAlphaHook.sol:285-289`
- **Gap description:** The code tracks `tickDelta^2` as the squared return, but never actually multiplies by `ln(1.0001)^2` (approximately `1e-8`). The variance is tracked in tick-space units, not in actual log-return space. This is internally consistent (fee yield and IL cost are both computed in tick-space), so the comparison is valid. However, the NatSpec implies the values are in log-return space, which is misleading. The `getVolEstimate` view function (line 402) returns `annualizedVol = hourlyVar * 8760` which would be meaningless in tick-space units to external consumers.
- **Risk assessment:** Low. Internal comparisons are consistent. External consumers of `getVolEstimate()` would get incorrect absolute vol values (off by a factor of ~1e-8), which could mislead off-chain monitoring or integrators.

### 1.7 ILAlphaVault: "ERC-4626 vault" / "implements virtual shares (1e6 offset)"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaVault.sol:20-22`
- **Code reference:** `BaseVault.sol:15-16` — `VIRTUAL_SHARES = 1e6`, `VIRTUAL_ASSETS = 1e6`
- **Assessment:** Virtual share offset is implemented in all conversion functions.

### 1.8 ILAlphaVault: "Depositor -> deposit(USDC) -> vault holds idle"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaVault.sol:26`
- **Code reference:** `ILAlphaVault.sol:152-163` — deposit transfers assets; vault holds idle until rebalance
- **Assessment:** Deposit only holds assets. Rebalance is a separate step.

### 1.9 ILAlphaVault: "Conservative threshold — Gamma's lax check led to $6.4M exploit"

- **Status:** PARTIAL
- **Spec reference:** `ILAlphaVault.sol:336`
- **Code reference:** `ILAlphaVault.sol:337-355`
- **Gap description:** The TWAP check uses `volOracles[poolId].lastTick` as a proxy for historical price, which is updated on every swap (line 300). This is NOT a TWAP — it is the tick from the last swap. In a low-liquidity pool, a single large swap could move `lastTick` to a manipulated price, and a follow-up transaction would pass the "TWAP" check because `spotTick` would now be close to the manipulated `lastTick`. The comment acknowledges "V4 doesn't have built-in observe() for TWAP" but calling this a TWAP check is misleading.
- **Risk assessment:** Medium. The check provides some protection against multi-block manipulation but is ineffective against same-block or consecutive-block sandwich attacks. The "conservative threshold" claim is debatable given the proxy approach.

### 1.10 AlwaysLPVault: "Control vault: always provides LP regardless of vol conditions"

- **Status:** NON-COMPLIANT
- **Severity:** Medium
- **Spec reference:** `AlwaysLPVault.sol:8-9`
- **Code reference:** `AlwaysLPVault.sol:28-47`
- **Gap description:** AlwaysLPVault does not actually provide LP to any Uniswap V4 pool. It merely tracks `deployedAssets` as an accounting variable and adds idle balance to it on `rebalance()`. No actual `poolManager.modifyLiquidity()` call exists. This means the "control vault" does not experience real IL, real fees, or real pool dynamics — making it useless as a benchmark comparison.
- **Risk assessment:** Low (security), High (product validity). The control comparison data will be meaningless because AlwaysLPVault never actually LPs. Any A/B comparison (ROADMAP.md Phase 3: "Monitor: ILAlpha vs AlwaysLP vs HODL") will be invalid.

### 1.11 HODLVault: "Control vault: just holds the deposit token, never provides LP"

- **Status:** COMPLIANT
- **Spec reference:** `HODLVault.sol:8-9`
- **Code reference:** `HODLVault.sol:15-17`
- **Assessment:** Correctly holds assets only, totalAssets = balance.

### 1.12 SwapHelper: "Helper for keeper bot to execute swaps"

- **Status:** COMPLIANT
- **Spec reference:** `SwapHelper.sol:13-14`
- **Code reference:** `SwapHelper.sol:33-98`
- **Assessment:** Correctly executes swaps via poolManager unlock callback pattern.

### 1.13 ILAlphaHook: "Volume spike multiplier: if single swap volume > 3x average -> emergency LP off"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:88-89`
- **Code reference:** `ILAlphaHook.sol:241,250-255`
- **Assessment:** Spike detection correctly compares abs amount against `ewmaVolume * SPIKE_MULTIPLIER` and bypasses cooldown.

### 1.14 ILAlphaVault: "Maximum total deposits allowed (default $10K USDC = 10_000e6)"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaVault.sol:78-79`
- **Code reference:** `ILAlphaVault.sol:79,160`
- **Assessment:** `depositCap = 10_000e6`, enforced in `deposit()`.

### 1.15 ILAlphaHook: "Cost: ~3.5K gas (1 SSTORE, packed slot)"

- **Status:** COMPLIANT (unverified exact number)
- **Spec reference:** `ILAlphaHook.sol:280`
- **Code reference:** `ILAlphaHook.sol:281-304`
- **Assessment:** Single packed struct write. Gas estimate is plausible. Would need profiling to verify exact 3.5K figure.

---

## 2. ERC-4626 Compliance

### 2.1 Required Functions

| Function | Status | Notes |
|----------|--------|-------|
| `deposit(uint256, address)` | COMPLIANT | Overridden in ILAlphaVault with guards; calls `super.deposit` |
| `withdraw(uint256, address, address)` | COMPLIANT | Inherited from solmate ERC4626 |
| `mint(uint256, address)` | NON-COMPLIANT | See 2.2 |
| `redeem(uint256, address, address)` | NON-COMPLIANT | See 2.3 |
| `convertToShares(uint256)` | COMPLIANT | Overridden in BaseVault with virtual offset |
| `convertToAssets(uint256)` | COMPLIANT | Overridden in BaseVault with virtual offset |
| `previewDeposit(uint256)` | COMPLIANT | Uses `convertToShares` |
| `previewMint(uint256)` | COMPLIANT | Uses virtual offset with `mulDivUp` |
| `previewWithdraw(uint256)` | COMPLIANT | Uses virtual offset with `mulDivUp` |
| `previewRedeem(uint256)` | COMPLIANT | Uses `convertToAssets` |
| `maxDeposit(address)` | COMPLIANT | Overridden to enforce deposit cap |
| `maxMint(address)` | PARTIAL | See 2.4 |
| `maxWithdraw(address)` | COMPLIANT | Inherited from solmate |
| `maxRedeem(address)` | COMPLIANT | Inherited from solmate |
| `totalAssets()` | COMPLIANT | Overridden with real-time LP valuation |

### 2.2 `mint()` Bypasses Guards

- **Status:** NON-COMPLIANT
- **Severity:** High
- **Spec reference:** `ILAlphaVault.sol:20` — "ERC-4626 vault"
- **Code reference:** Solmate `ERC4626.sol:60-71` (inherited, not overridden)
- **Gap description:** `ILAlphaVault.deposit()` adds `whenNotPaused`, `nonReentrant`, `DepositTooSmall`, `DepositCapExceeded`, and `_checkTWAP()` guards. However, `mint()` is not overridden and inherits the unguarded solmate implementation directly. A user can call `mint()` to bypass all protections: paused state, reentrancy guard, minimum deposit check, deposit cap, and TWAP manipulation check.
- **Risk assessment:** Critical. This is a direct security bypass. An attacker can mint shares while the vault is paused, exceed the deposit cap, or deposit during price manipulation — all protections the developer explicitly added are circumvented.

### 2.3 `redeem()` Bypasses beforeWithdraw Fee

- **Status:** NON-COMPLIANT
- **Severity:** Medium
- **Spec reference:** `ILAlphaVault.sol:299-312` — `beforeWithdraw` applies withdrawal fee and TWAP check
- **Code reference:** Solmate `ERC4626.sol:95-116` — `redeem()` calls `beforeWithdraw(assets, shares)` correctly
- **Gap description:** Actually, `redeem()` does call `beforeWithdraw` via solmate. However, there is a subtler issue: `beforeWithdraw` accumulates the withdrawal fee (`accumulatedFees += fee`) but does NOT reduce the assets transferred to the receiver. The user still receives the full `assets` amount. The fee accounting inflates `accumulatedFees` without a corresponding deduction from the transfer, meaning `claimFees()` will attempt to transfer tokens that do not exist (or will transfer tokens that belong to other depositors).
- **Risk assessment:** High. The withdrawal fee mechanism is broken. `beforeWithdraw` records a fee but never deducts it from the withdrawal. When `claimFees()` is called, it transfers assets that may belong to other depositors, effectively stealing from the pool. Over time, `accumulatedFees` grows but the vault's total assets shrink only by the actual withdrawals (not withdrawals + fees), creating an accounting insolvency.

### 2.4 `maxMint()` Does Not Respect Deposit Cap

- **Status:** PARTIAL
- **Spec reference:** ERC-4626 spec requires `maxMint` to return the maximum shares that can be minted
- **Code reference:** Inherited from solmate: returns `type(uint256).max`
- **Gap description:** `maxDeposit()` correctly caps at `depositCap - totalAssets()`, but `maxMint()` returns `type(uint256).max`. Per ERC-4626, `maxMint` should be consistent with `maxDeposit`. Since `mint()` is also unguarded (Finding 2.2), this is doubly incorrect.
- **Risk assessment:** Low (given that mint is already completely unguarded). Violates ERC-4626 specification.

---

## 3. Uniswap V4 Hook Interface

### 3.1 Hook Permissions and Selectors

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:147-149` — "Only afterInitialize and afterSwap are active"
- **Code reference:** `ILAlphaHook.sol:126-144` — `Hooks.Permissions` struct sets only `afterInitialize: true` and `afterSwap: true`
- **Assessment:** All 14 IHooks functions are implemented. Active hooks (`afterInitialize`, `afterSwap`) have logic; all others return their selector as no-ops. Selectors are correctly returned.

### 3.2 afterSwap Signature

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:220-262`
- **Assessment:** Matches the V4 IHooks interface: `(address, PoolKey calldata, SwapParams calldata, BalanceDelta, bytes calldata) -> (bytes4, int128)`. Returns `(selector, 0)` — no delta modification.

### 3.3 afterInitialize Signature

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:155-186`
- **Assessment:** Correct V4 signature. Initializes oracle and pool state.

### 3.4 No-op Hooks

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:151,188-274`
- **Assessment:** All non-active hooks are `pure` functions returning correct selectors. No reverts.

### 3.5 beforeSwap Return Type

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:214-218`
- **Assessment:** Returns `(bytes4, BeforeSwapDelta, uint24)` matching V4 interface.

### 3.6 afterAddLiquidity / afterRemoveLiquidity Return Types

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:194-212`
- **Assessment:** Returns `(bytes4, BalanceDelta)` with zero delta. Matches V4 interface.

### 3.7 onlyPoolManager Guard

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:105-108`, applied to `afterInitialize` and `afterSwap`
- **Assessment:** Active hooks are properly gated. No-op hooks are `pure` (safe either way).

### 3.8 IUnlockCallback Implementation (ILAlphaVault)

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:211-222`
- **Assessment:** `unlockCallback` is gated with `OnlyPoolManager` check. Uses `_pendingAction` enum to disambiguate callback context.

---

## 4. Mathematical Claims

### 4.1 "EWMA of squared log-returns" (Variance Oracle)

- **Status:** COMPLIANT (with caveat from 1.6)
- **Spec reference:** `ILAlphaHook.sol:59` — `EWMA of squared log-returns (variance), scaled 1e18`
- **Code reference:** `ILAlphaHook.sol:281-304`
- **Verification:**
  ```
  tickDelta = currentTick - lastTick
  squaredReturn = tickDelta^2 * 1e18              // squared tick-space return
  squaredReturn = squaredReturn * 3600 / elapsed   // time-normalize to per-hour
  newVar = (lambda * oldVar + (1 - lambda) * squaredReturn) / BPS
  ```
  This is a correct EWMA update formula: `EWMA_new = lambda * EWMA_old + (1 - lambda) * observation`. The time-normalization to per-hour is correct. Values are in tick-space, not log-return space (see Finding 1.6).

### 4.2 "gamma exposure model: IL_cost approx 0.5 * sigma^2 * concentration"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:82` — `IL_cost approx 0.5 * sigma^2 * concentration`
- **Code reference:** `ILAlphaHook.sol:336`
- **Verification:**
  ```
  GAMMA_FACTOR = 5e17  // 0.5 in 1e18
  concentration = (10_000 * 1e18) / tickRange
  ilCost = (GAMMA_FACTOR * ewmaVar * concentration) / (1e18 * 1e18)
         = 0.5 * ewmaVar * concentration / 1e18
  ```
  This matches the stated formula. The concentration factor is proportional to `1/tickRange`, which is a standard approximation for concentrated liquidity IL amplification. The `10_000` constant is an arbitrary scaling factor for the concentration, effectively a tuning parameter.

### 4.3 "fee_yield = poolFee * ewmaVolume"

- **Status:** NON-COMPLIANT
- **Severity:** Medium
- **Spec reference:** `ILAlphaHook.sol:319` — `fee_yield = poolFee * ewmaVolume (volume-weighted fee income proxy)`
- **Code reference:** `ILAlphaHook.sol:329`
- **Verification:**
  ```
  feeYield = (poolFee * ewmaVolume) / 1_000_000
  ```
  The comment says `poolFee is in hundredths of a bip (3000 = 0.30%)`. However, Uniswap V4 pool fees are in hundredths of a bip, so 3000 = 0.30% = 0.003. Dividing by `1_000_000` converts correctly: `3000 / 1_000_000 = 0.003`. The formula is arithmetically correct.

  However, there is a **units mismatch** between `feeYield` and `ilCost`:
  - `feeYield` is in token units (fee rate * volume in token units)
  - `ilCost` is in tick-space variance units (GAMMA_FACTOR * tick^2 * concentration)

  These are not comparable quantities. The comparison `feeYield > ilCost` compares token-denominated fee income against tick-space-denominated IL cost. Whether this comparison produces correct LP on/off decisions depends entirely on the relative magnitudes, which are not theoretically grounded. It may work in practice by coincidence of parameter tuning, but the dimensional analysis is wrong.
- **Risk assessment:** Medium. The core strategy decision (LP on vs LP off) is based on comparing dimensionally inconsistent quantities. This could lead to systematically wrong LP decisions for pools with unusual fee tiers, volumes, or tick ranges.

### 4.4 Virtual Shares (1e6 offset) — Inflation Attack Defense

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaVault.sol:22` — "Implements virtual shares (1e6 offset) for inflation attack defense"
- **Code reference:** `BaseVault.sol:15-16,22-32`
- **Verification:** The virtual shares pattern adds `VIRTUAL_SHARES = 1e6` to supply and `VIRTUAL_ASSETS = 1e6` to total assets in all conversion functions. This is the standard OpenZeppelin-recommended defense against ERC-4626 inflation attacks. With a 1e6 offset, an attacker would need to donate at least 1e6 units of the asset token to extract 1 unit of profit, making the attack economically infeasible for tokens with 6+ decimals (like USDC).
- **Risk assessment:** Defense is effective for USDC (6 decimals). For 18-decimal tokens, the offset is relatively smaller but still provides meaningful protection (attacker needs 1e6 wei donation per 1 wei extracted).

### 4.5 Annualized Vol Calculation

- **Status:** PARTIAL
- **Spec reference:** `ILAlphaHook.sol:402` — `annualizedVol = hourlyVar * 8760`
- **Code reference:** `ILAlphaHook.sol:402`
- **Gap description:** Annualized variance should be `hourlyVar * 8760` (variance scales linearly with time). However, this gives annualized VARIANCE, not annualized VOLATILITY. The variable name says `annualizedVol` (volatility), which would require `sqrt(hourlyVar * 8760)`. This is a naming/documentation error, not a security issue (the value is only used in a view function).
- **Risk assessment:** Low. Only affects off-chain consumers who interpret the return value as volatility instead of variance.

---

## 5. Stated Security Properties

### 5.1 "Rate limited: max change per push is 2x current value"

- **Status:** NON-COMPLIANT (duplicate of Finding 1.5)
- **Severity:** Critical
- **Details:** See Finding 1.5. Code allows 2.5x effective change per push, not 2x.

### 5.2 "Only provide liquidity when fee yield > IL cost"

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:16-17`, `CLAUDE.md:6`
- **Code reference:** `ILAlphaHook.sol:345`, `ILAlphaVault.sol:177`
- **Assessment:** The hook toggles `isLPActive` based on the fee/IL comparison. The vault reads `hook.isLPActive()` in `rebalance()` to decide whether to add/remove liquidity. The chain of control is correct.

### 5.3 "Conservative threshold" for TWAP

- **Status:** PARTIAL (duplicate of Finding 1.9)
- **Details:** See Finding 1.9. The "TWAP" check uses last swap tick as proxy, which is not actually conservative.

### 5.4 Two-Step Ownership Transfer

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:426-440`, `ILAlphaVault.sol:391-401`
- **Assessment:** Both contracts implement two-step ownership with `transferOwnership` -> `acceptOwnership`. Correctly prevents accidental ownership transfer to wrong address.

### 5.5 Cooldown Period

- **Status:** COMPLIANT
- **Spec reference:** `ILAlphaHook.sol:78` — `COOLDOWN_SECONDS = 24 hours`
- **Code reference:** `ILAlphaHook.sol:257` — `block.timestamp >= ps.lastToggleTime + COOLDOWN_SECONDS`
- **Assessment:** 24-hour cooldown between LP toggles. Volume spike emergency bypass is intentional and documented.

---

## 6. Missing Implementations

### 6.1 Idle Capital Yield (Aave/Compound Routing)

- **Status:** MISSING
- **Spec reference:** `COMPETITIVE.md:151` — "Routing idle funds to Aave/Compound for lending yield during off periods would add 3-5% base APY. No competitor does this."
- **Gap description:** Mentioned as a Phase 5-6 feature. No code or interface exists for this.
- **Risk assessment:** None (future feature, correctly scoped as Phase 5-6).

### 6.2 Performance Fee / Management Fee

- **Status:** MISSING
- **Severity:** Informational
- **Spec reference:** `ROADMAP.md:51-66` — Phased fee structure: 10% performance fee at launch
- **Code reference:** `ILAlphaVault.sol:84-88` — Only withdrawal fee exists (0.1%)
- **Gap description:** The roadmap describes a performance fee model (10-20% of excess returns) and management fee (0-1%/yr). The code only implements a flat withdrawal fee (0.1%). No high-water mark, no performance fee calculation, no management fee accrual.
- **Risk assessment:** Informational. Revenue model is not yet implemented. The withdrawal fee is a placeholder.

### 6.3 Multi-Pool Support

- **Status:** MISSING
- **Spec reference:** `ROADMAP.md:114-121` — Risk-ascending multi-pool expansion (wstETH/ETH, USDC/USDT, ETH/USDC, BTC/ETH)
- **Code reference:** `ILAlphaVault.sol:67-68` — Single `poolKey` storage variable
- **Gap description:** The vault supports only one pool. The hook supports multiple pools (via `mapping(PoolId => ...)`), but the vault is single-pool.
- **Risk assessment:** Informational. Correctly scoped as future work.

### 6.4 AlwaysLPVault Does Not Actually LP

- **Status:** MISSING (duplicate of Finding 1.10)
- **Spec reference:** `ROADMAP.md:23` — "AlwaysLPVault - always LP active, no hook"
- **Gap description:** The control vault must actually interact with a Uniswap V4 pool to provide meaningful benchmark data. Currently it is a no-op accounting vault.

---

## 7. Additional Findings

### 7.1 Withdrawal Fee Does Not Reduce Assets Sent to User

- **Status:** NON-COMPLIANT
- **Severity:** Critical (duplicate of Finding 2.3)
- **Code reference:** `ILAlphaVault.sol:299-312`
- **Details:** `beforeWithdraw` computes and accumulates a fee but does not deduct it from the withdrawal amount. The solmate `withdraw()` function (line 92) sends the full requested `assets` to the receiver regardless. The fee is phantom accounting — it records a liability without creating a corresponding asset.

### 7.2 `withdraw()` and `redeem()` Missing Guards

- **Status:** NON-COMPLIANT
- **Severity:** Medium
- **Code reference:** Solmate `ERC4626.sol:73-116` (inherited, not overridden)
- **Gap description:** `deposit()` is protected with `whenNotPaused` and `nonReentrant`, but `withdraw()` and `redeem()` inherit directly from solmate without these guards. While `beforeWithdraw` adds a TWAP check, the reentrancy and pause guards are missing. A user can withdraw during a paused state (only deposits are blocked when paused, not withdrawals).
- **Risk assessment:** Medium. Withdrawals during pause may be intentional (allowing users to exit during emergency), but the asymmetry is not documented. The missing `nonReentrant` on `withdraw()`/`redeem()` is more concerning — the `beforeWithdraw` hook calls `_removeLiquidity()` which calls `poolManager.unlock()`, creating a complex call chain that could have reentrancy implications through the callback.

### 7.3 `_pendingAction` State Could Be Manipulated

- **Status:** COMPLIANT (no external attack vector)
- **Code reference:** `ILAlphaVault.sol:91-92,198-208`
- **Assessment:** `_pendingAction` is set and cleared within the same transaction. The `unlockCallback` is gated by `onlyPoolManager`. No external manipulation vector exists because `_pendingAction` is private and only the pool manager can call `unlockCallback`.

---

## Risk Summary

### Critical (3)

1. **Finding 1.5/5.1:** Rate limit documentation says 2x but code allows 2.5x effective change per `pushVolEstimate` call. Compromised keeper can ramp vol faster than documented.
2. **Finding 2.2:** `mint()` bypasses all deposit guards (pause, reentrancy, TWAP check, deposit cap, minimum deposit).
3. **Finding 2.3/7.1:** Withdrawal fee accounting is broken — fee is recorded but never deducted from withdrawal, leading to insolvency when `claimFees()` is called.

### High (3)

4. **Finding 1.10/6.4:** AlwaysLPVault does not actually LP, making the control benchmark meaningless.
5. **Finding 4.3:** Fee yield vs IL cost comparison uses dimensionally inconsistent units (tokens vs tick-space).
6. **Finding 7.2:** `withdraw()`/`redeem()` missing `nonReentrant` guard despite complex callback chain in `beforeWithdraw`.

### Medium (4)

7. **Finding 1.9/5.3:** "TWAP" check uses last swap tick as proxy — not a real TWAP, vulnerable to same-block manipulation.
8. **Finding 2.4:** `maxMint()` returns `type(uint256).max`, inconsistent with deposit cap.
9. **Finding 4.3:** Units mismatch may cause systematically wrong LP decisions for certain pool configurations.
10. **Finding 7.2:** Withdrawals work while paused (asymmetric guard — may be intentional but undocumented).

### Low (4)

11. **Finding 1.6:** EWMA variance tracked in tick-space, not log-return space — misleading NatSpec.
12. **Finding 4.4:** View function returns variance labeled as "annualizedVol".
13. **Finding 4.5:** `getVolEstimate` returns meaningless values for external consumers.
14. **Finding 2.4:** `maxMint` violates ERC-4626 consistency requirement.

### Informational (3)

15. **Finding 6.1:** Idle capital yield routing is future work (Phase 5-6).
16. **Finding 6.2:** Performance/management fee model not implemented yet.
17. **Finding 6.3:** Multi-pool vault support not implemented yet.

---

## Recommendations

1. **Fix `mint()` bypass (Critical):** Override `mint()` in `ILAlphaVault` with the same guards as `deposit()`.
2. **Fix withdrawal fee (Critical):** Either deduct the fee from the transferred amount (override `withdraw`/`redeem` to send `assets - fee`) or remove the fee mechanism entirely.
3. **Fix rate limit (Critical):** Change `currentVar * 4` to `currentVar * 3` to achieve the documented 2x max effective change, or update the NatSpec to say "2.5x".
4. **Add reentrancy guard to withdraw/redeem (High):** Override both functions to add `nonReentrant`.
5. **Document units (Medium):** Clarify that the fee/IL comparison is a heuristic in tick-space units, not a rigorous financial calculation.
6. **Implement real AlwaysLPVault (High):** Connect to actual Uniswap V4 pool for meaningful benchmarking.
7. **Consider actual TWAP (Medium):** Implement a sliding-window tick accumulator for real TWAP instead of last-tick proxy.
