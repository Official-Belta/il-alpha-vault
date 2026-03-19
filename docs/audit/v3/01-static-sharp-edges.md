# IL Alpha Vault -- V3 Static Analysis + Sharp Edges

**Date:** 2026-03-20
**Scope:** ILAlphaHook.sol, ILAlphaVault.sol, BaseVault.sol (post-V2 fix)
**Method:** Combined static analysis and sharp-edges pass, verifying V2 remediations

---

## V2 Finding Verification

### R-1: ERC-4626 Non-Conformance in withdraw/redeem

- **Severity:** HIGH
- **Status:** FIXED
- **File:** `ILAlphaVault.sol:327-339`
- **Analysis:** Withdrawal fee has been completely removed. `withdraw()` and `redeem()` now simply call `_checkTWAP()` then delegate to `super.withdraw()` / `super.redeem()` (solmate ERC4626). The base solmate implementation computes shares via `previewWithdraw`, burns them, and transfers exactly the requested `assets` amount. `previewWithdraw` and `previewRedeem` in BaseVault use the standard virtual-shares math with no fee distortion. The vault is now fully ERC-4626 conformant on withdrawal flow.

---

### R-2: `accumulatedFees` Not Subtracted from `totalAssets()`

- **Severity:** HIGH
- **Status:** FIXED
- **File:** `ILAlphaVault.sol:146-162`
- **Analysis:** `accumulatedFees` storage variable no longer exists. `totalAssets()` returns `idle + lpValue` with no phantom fee inflation. No `claimFees()` function exists. No fee-related storage or logic remains in any of the three contracts.

---

### R-3: TWAP Buffer Defeatable via Same-Block Multi-Swap

- **Severity:** MEDIUM-HIGH
- **Status:** FIXED
- **File:** `ILAlphaHook.sol:448-458`
- **Analysis:** Same-block deduplication has been added. The check at line 452:
  ```solidity
  uint8 prevIdx = idx == 0 ? TWAP_WINDOW - 1 : idx - 1;
  if (tickObservations[poolId][prevIdx].timestamp == uint40(block.timestamp)) return;
  ```
  On the first-ever call for a pool, `idx == 0`, so `prevIdx` wraps to 9. `tickObservations[poolId][9]` is default-initialized with `timestamp == 0`, which is not equal to `block.timestamp`, so the first observation writes correctly. On subsequent same-block swaps, `prevIdx` points to the slot just written (which has the current `block.timestamp`), so the function returns early. The dedup logic is correct.

---

### R-4: No Slippage Protection on LP Removal

- **Severity:** MEDIUM
- **Status:** PARTIALLY FIXED (Acknowledged)
- **File:** `ILAlphaVault.sol:306-322`
- **Description:** `_executeRemoveLiquidity` computes `estValue0` and `estValue1` via `_getDeployedLPValue()` (line 318) but explicitly does NOT call `_checkSlippage`. The comment at line 319 explains: "Not checking slippage on removal to avoid bricking emergency withdraw. The TWAP check on withdraw already provides sandwich protection." The estimated values are computed but never used -- this is dead code.
- **Recommendation:** Either remove the dead `_getDeployedLPValue()` call (saves ~5K gas on every removal) or add an opt-out slippage check that the emergency path can bypass. Current approach relies solely on TWAP, which degrades when observations are stale (see R-7 below).

---

### R-5: `_checkSlippage` Sums Different-Decimal Tokens

- **Severity:** MEDIUM
- **Status:** NOT FIXED
- **File:** `ILAlphaVault.sol:349-353`
- **Description:** `_checkSlippage` sums `uint128(-d0)` and `uint128(-d1)` into `actualCost`, then compares against `expected` (which is in asset-token decimals). If token0 is USDC (6 decimals) and token1 is WETH (18 decimals), the sum is meaningless. Example: paying 100e6 USDC + 0.05e18 WETH = 100_000_000 + 50_000_000_000_000_000 -- the WETH term dominates and the check always reverts or is always too lax depending on direction.
- **Impact:** Slippage check is unreliable for pairs with different decimals. For same-decimal pairs (e.g., USDC/USDT), it works correctly.
- **Recommendation:** Compare only the asset-token side of the delta against `expected`, ignoring the non-asset token. This aligns with the conservative `totalAssets()` approach that already counts only the asset token.

---

### R-6: `setMaxSlippageBps(0)` Bricks LP Rebalancing

- **Severity:** MEDIUM
- **Status:** FIXED
- **File:** `ILAlphaVault.sol:476-481`
- **Analysis:** Range validation added: `require(_bps >= 10 && _bps <= 500, "Range: 10-500 bps")`. Minimum 10 bps (0.1%) prevents bricking. Maximum 500 bps (5%) prevents owner from setting an absurdly loose check.

---

### R-7: TWAP Fallback Degrades to V1 Behavior

- **Severity:** MEDIUM
- **Status:** NOT FIXED (Acknowledged)
- **File:** `ILAlphaHook.sol:480-483`
- **Description:** When `totalWeight == 0` (all observations are >1hr old or uninitialized), `getTwapTick` returns `volOracles[poolId].lastTick`. The comment says "deviation=0 and pass" but this is only true when `spotTick == lastTick`. In practice, `_checkTWAP` computes `deviation = |spotTick - twapTick|`. If `lastTick` happens to be close to `spotTick`, the check passes trivially -- providing no manipulation protection. This is exactly the V1 weakness.
- **Nuance:** The `_checkTWAP` in ILAlphaVault (line 378) returns early if `deployedLiquidity == 0`, so the fallback only matters when LP is deployed AND observations are stale (e.g., no swaps for >1 hour). In such low-activity pools, sandwich risk is lower, partially mitigating the concern.
- **Recommendation:** Consider reverting when no valid TWAP observations exist instead of silently degrading. Alternatively, widen the staleness window beyond 1 hour.

---

### R-8: `setMaxSlippageBps` Missing Event

- **Severity:** LOW
- **Status:** FIXED
- **File:** `ILAlphaVault.sol:65, 479`
- **Analysis:** `SlippageUpdated` event declared at line 65 and emitted at line 479 with old and new values.

---

### R-9: `mint()` calls `previewMint` twice

- **Severity:** LOW (gas)
- **Status:** NOT FIXED
- **File:** `ILAlphaVault.sol:185, 189`
- **Description:** `mint()` calls `previewMint(shares)` at line 185 for the deposit-cap check, then `super.mint(shares, receiver)` at line 189 which calls `previewMint` again inside solmate's `mint()`. Double SLOAD of `totalAssets()` (which reads pool state) wastes ~5-10K gas.

---

### R-10: `PoolKeyUpdated` event has no parameters

- **Severity:** LOW
- **Status:** NOT FIXED
- **File:** `ILAlphaVault.sol:66`
- **Description:** `event PoolKeyUpdated()` is declared with no parameters and is never emitted. `setPoolKey()` (line 442-451) does not emit it. This is both dead code and a missing event emission.

---

### R-11: `beforeWithdraw` removes ALL LP even for small shortfalls

- **Severity:** LOW
- **Status:** NOT FIXED (by design)
- **File:** `ILAlphaVault.sol:341-346`
- **Description:** When `idle < assets`, the entire LP position is removed regardless of the shortfall size. A 1 USDC shortfall on a 10,000 USDC LP position triggers full removal. This is by design (partial removal adds complexity and gas), but worth noting for operational awareness.

---

## New V3 Findings

### V3-1: `setPoolKey` Does Not Emit `PoolKeyUpdated` Event

- **Severity:** LOW
- **Status:** NEW
- **File:** `ILAlphaVault.sol:442-451, 66`
- **Description:** The `PoolKeyUpdated` event is declared at line 66 but `setPoolKey()` never emits it. This is dead code and a monitoring gap -- off-chain systems cannot detect pool key changes.
- **Fix:** Add `emit PoolKeyUpdated();` at the end of `setPoolKey()`, or better, add the old/new pool ID as parameters.

---

### V3-2: Dead Code in `_executeRemoveLiquidity`

- **Severity:** INFO
- **Status:** NEW
- **File:** `ILAlphaVault.sol:318`
- **Description:** Line 318 calls `_getDeployedLPValue()` and assigns to `(estValue0, estValue1)`, but these values are never read. This is ~5K gas wasted on every LP removal (two external calls to PoolManager + tick math). Left over from when R-4 slippage check was planned but then intentionally skipped.
- **Fix:** Remove the call entirely, or add a comment explaining it is intentionally retained for future use.

---

### V3-3: `_checkSlippage` Only Called on Add, Not Remove

- **Severity:** INFO
- **Status:** NEW (related to R-4)
- **File:** `ILAlphaVault.sol:268, 306-322`
- **Description:** Architectural note: `_checkSlippage` is called in `_executeAddLiquidity` (line 268) but not in `_executeRemoveLiquidity`. The comment explains the rationale (avoid bricking emergency withdraw). However, `emergencyWithdraw()` calls `_removeLiquidity()` directly, so a flag-based approach could enable slippage checks on normal removal while bypassing for emergency.

---

### V3-4: Stale Comment References Fee Logic

- **Severity:** INFO
- **Status:** NEW
- **File:** `ILAlphaVault.sol:324`
- **Description:** Line 324 comment says `"H-5: reentrancy, no fee -- fee deferred post-audit"`. The fee was not deferred -- it was removed entirely in V3. Comment should be updated to reflect the current design intent.

---

### V3-5: `_checkTWAP` Skipped When `deployedLiquidity == 0` on Withdraw

- **Severity:** INFO
- **Status:** NEW
- **File:** `ILAlphaVault.sol:378-379`
- **Description:** When no LP is deployed, `_checkTWAP` returns immediately without checking price manipulation. This is acceptable because with no LP deployed, `totalAssets() == idle balance` which cannot be manipulated via pool price. However, if `beforeWithdraw` triggers `_removeLiquidity` (setting `deployedLiquidity = 0`), the TWAP check in `withdraw()` has already run before `beforeWithdraw` executes (solmate calls `beforeWithdraw` after share computation). The ordering is: `_checkTWAP` (line 330) -> `super.withdraw` -> `previewWithdraw` -> `beforeWithdraw` -> `_burn` -> `transfer`. This is correct: TWAP is checked while LP is still deployed, before removal.

---

## Summary

| ID | Severity | Status | Description |
|----|----------|--------|-------------|
| R-1 | HIGH | FIXED | ERC-4626 non-conformance (fee removed) |
| R-2 | HIGH | FIXED | accumulatedFees phantom in totalAssets (fee removed) |
| R-3 | MED-HIGH | FIXED | TWAP same-block dedup added |
| R-4 | MEDIUM | PARTIAL | Remove slippage: intentionally skipped, dead code remains |
| R-5 | MEDIUM | NOT FIXED | Cross-decimal slippage sum still present |
| R-6 | MEDIUM | FIXED | setMaxSlippageBps now bounded 10-500 |
| R-7 | MEDIUM | NOT FIXED | TWAP fallback still returns lastTick |
| R-8 | LOW | FIXED | SlippageUpdated event added |
| R-9 | LOW | NOT FIXED | Double previewMint call in mint() |
| R-10 | LOW | NOT FIXED | PoolKeyUpdated: no params, never emitted |
| R-11 | LOW | NOT FIXED | Full LP removal on any shortfall (by design) |
| V3-1 | LOW | NEW | setPoolKey never emits PoolKeyUpdated |
| V3-2 | INFO | NEW | Dead estValue0/estValue1 in _executeRemoveLiquidity |
| V3-3 | INFO | NEW | Slippage check asymmetry (add vs remove) |
| V3-4 | INFO | NEW | Stale comment references deferred fee |
| V3-5 | INFO | NEW | _checkTWAP ordering analysis (correct) |

**V2 -> V3 improvement:** 4 of 8 V2 findings fully fixed (R-1, R-2, R-3, R-6, R-8 = 5 fixed). R-4 partially addressed. R-5 and R-7 remain open. No regressions introduced.

**Remaining action items (pre-mainnet):**
1. R-5: Fix `_checkSlippage` to compare only asset-token delta (~15 min)
2. R-7: Decide on TWAP fallback policy -- revert vs degrade (~10 min)
3. V3-1: Emit `PoolKeyUpdated` in `setPoolKey` (~2 min)
4. V3-2: Remove dead `_getDeployedLPValue()` call in removal (~2 min)
5. V3-4: Update stale fee comment (~1 min)
