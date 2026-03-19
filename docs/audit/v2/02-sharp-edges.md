# Sharp Edges Analysis v2 (Re-Audit) -- IL Alpha Vault

**Methodology:** Trail of Bits "sharp edges" framework
**Date:** 2026-03-20
**Scope:** All 6 contracts in `contracts/src/`
**Auditor:** Claude Opus 4.6 (automated)
**Baseline:** `docs/audit/02-sharp-edges.md` (v1)

---

## Part 1: Verification of v1 Fixes

| v1 ID  | Finding | Status | Notes |
|--------|---------|--------|-------|
| SE-01  | `setTwapThreshold` accepts zero/negative | **FIXED** | Now bounds-checked: `_threshold >= 10 && _threshold <= 2000`, reverts `TwapThresholdOutOfRange()`. Event emitted. |
| SE-02  | Withdrawal fee accounted but never deducted | **FIXED** | `withdraw()` and `redeem()` fully overridden. Fee deducted from transferred amount: `asset.safeTransfer(receiver, assets - fee)`. Solmate's default `withdraw`/`redeem` no longer called for the fee-bearing path. |
| SE-03  | `setPoolKey` allows change while LP deployed | **FIXED** | Guard added: `if (deployedLiquidity > 0) revert LPStillDeployed()`. |
| SE-04  | `_checkTWAP` uses stale `lastTick` as TWAP proxy | **FIXED** | Real TWAP implemented via circular buffer `tickObservations[10]` with recency-weighted average in `getTwapTick()`. See new findings below for residual issues. |
| SE-05  | `SwapHelper` uses raw `transferFrom` | **FIXED** | Now uses `SafeTransferLib.safeTransferFrom()` throughout. |
| SE-06  | `setKeeper(address(0))` allowed | **FIXED** | Both `ILAlphaHook.setKeeper` and `ILAlphaVault.setKeeper` now have `require(_keeper != address(0), "Zero address")`. `KeeperUpdated` event emitted in vault. |
| SE-07  | `pushVolEstimate` allows 4x jump | **FIXED** | `maxExternal` now `currentVar * 2` (was `currentVar * 4`). Baseline for zero changed to `1e18`. Max blended result is now `(currentVar + 2*currentVar)/2 = 1.5x`, consistent with conservative intent. |
| SE-08  | `totalAssets()` sums token0+token1 without price conversion | **FIXED** | Now only counts LP value in the vault's asset token. Conservative approach -- understates totalAssets when LP holds the other token, protecting share price. |
| SE-09  | `AlwaysLPVault.rebalance()` double-counts via `deployedAssets` | **FIXED** | `deployedAssets` tracking removed entirely. `totalAssets()` = `asset.balanceOf(address(this))`. Rebalance is now a no-op that emits an event. |
| SE-10  | No reentrancy guard on `withdraw`/`redeem` | **FIXED** | Both overridden with `nonReentrant` modifier. |
| SE-11  | `setDepositCap(0)` bricks deposits | **OPEN (Accepted)** | No minimum cap enforced. Setting to 0 still blocks all deposits. However, `DepositCapUpdated` event is now emitted, providing off-chain visibility. Acceptable given owner trust model. |
| SE-12  | Vol oracle noise amplification for small elapsed | **OPEN** | No minimum elapsed floor added. Still amplifies by `3600/elapsed`. See cross-cutting notes. |
| SE-13  | Negative tick rounding in `afterInitialize` | **OPEN** | Floor division not implemented. Solidity truncation toward zero still produces misaligned lower ticks for some negative tick values. Low severity -- `modifyLiquidity` will revert, forcing manual `setLPRange`. |
| SE-14  | `claimFees` does not verify balance | **FIXED** | Now uses `min(fees, available)` pattern. See new finding SE-v2-04 below. |
| SE-15  | `emergencyWithdraw` does not reset `accumulatedFees` | **OPEN** | `accumulatedFees` is still not reset. Post-emergency `claimFees` could drain user funds. Mitigated by the `min(fees, available)` fix, but `accumulatedFees` remains a phantom debt. |
| SE-16  | 50/50 split is naive -- vault may not hold both tokens | **OPEN (Known)** | Documented as `H-3 NOTE: Phase 4: pre-swap`. Not yet implemented. LP provisioning will revert if vault lacks the non-asset token. |
| SE-17  | `transferOwnership(address(0))` | **FIXED** | Both contracts now have `require(newOwner != address(0), "Zero address")`. |
| SE-18  | `SwapHelper` stale pending state | **OPEN** | State is still not cleared after callback. Stale `_pending*` values remain in storage. Low risk since `_locked` prevents reentry, but wastes gas on cold slot reads. |
| SE-19  | `setLPRange` tick spacing alignment | **FIXED** | Now validates `tickLower % spacing == 0 && tickUpper % spacing == 0`. |
| SE-20  | `getVolEstimate` annualization is naive | **OPEN** | Still multiplies variance by 8760 and calls it "Vol". View-only, no on-chain impact. |
| SE-21  | `HODLVault` no access controls | **OPEN (By Design)** | Intentional for benchmark. No change needed. |
| SE-22  | `AlwaysLPVault.beforeWithdraw` zeroes all `deployedAssets` | **FIXED (Removed)** | `deployedAssets` no longer exists. `AlwaysLPVault` is now a pure pass-through. |
| SE-23  | `COOLDOWN_SECONDS` typed `uint24` | **OPEN** | Still `uint24`. Compile-safe for 86400. Cosmetic. |

**Summary:** 13 of 23 findings fixed. 4 open-accepted/by-design. 6 still open (low/medium severity).

---

## Part 2: New Sharp Edges Introduced by Fixes

### SE-v2-01: Withdraw/redeem override bypasses solmate's `beforeWithdraw` -- dead code path

- **Severity:** LOW
- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:388-389`
- **Description:** The `beforeWithdraw` override is now an intentionally empty function (comment: "logic moved to withdraw()/redeem() overrides"). This is correct for `ILAlphaVault`. However, `BaseVault` extends solmate's `ERC4626`, and solmate's default `withdraw()` and `redeem()` still exist as callable `public virtual` functions. The overridden `withdraw`/`redeem` in `ILAlphaVault` completely replace the parent logic (they do not call `super.withdraw`), which means:
  1. The `beforeWithdraw` hook is truly dead code -- it will never be called through the vault's own functions.
  2. Any future subclass of `ILAlphaVault` that expects `beforeWithdraw` to fire on withdrawals will be silently broken.
  3. The `afterDeposit` hook (from solmate) is also not overridden but is still live on the deposit path via `super.deposit()`. This asymmetry is confusing.
- **Side effect risk:** The overridden `withdraw` manually replicates solmate's allowance check and burn logic. If solmate's ERC4626 is upgraded (e.g., to add a new hook), the vault will not pick up the change because it bypasses `super.withdraw()`.
- **Impact:** No immediate vulnerability. Future maintenance hazard.
- **Recommendation:** Add a comment on `BaseVault` clarifying that subclasses overriding `withdraw`/`redeem` must not rely on `beforeWithdraw`. Consider marking `beforeWithdraw` as `override` with a revert to catch accidental calls.

### SE-v2-02: TWAP accumulator uses `TickObservation[10]` mapped by `PoolId` -- no storage collision but gas/correctness concerns

- **Severity:** MEDIUM
- **Category:** Design Misuse
- **File:** `ILAlphaHook.sol:114-115`
- **Description:** The TWAP implementation stores observations in `mapping(PoolId => TickObservation[10]) public tickObservations`. This is a fixed-size array inside a mapping, which Solidity handles correctly -- each PoolId maps to its own independent array in a unique storage slot (the slot is `keccak256(poolId . slot_of_mapping) + index`). **There is no storage collision risk.**

  However, the design has these concerns:

  **(a) Cold-start inaccuracy:** A freshly registered pool has all 10 observations initialized to `{tick: 0, timestamp: 0}`. The `getTwapTick` loop skips entries with `timestamp == 0`, but until 10 swaps have occurred, the TWAP is computed from fewer data points. With 1-2 observations, the "TWAP" is essentially a spot price, providing no manipulation resistance.

  **(b) Sparse observation problem:** If the pool has low swap frequency (e.g., 1 swap per hour), the 10-slot buffer covers 10 hours. But `getTwapTick` filters out observations older than 3600 seconds (1 hour). In a low-activity pool, only 1-2 observations will be within the window, again degenerating to near-spot.

  **(c) All observations in same block:** In a sandwich attack, the attacker can execute multiple swaps in the same block. Each swap writes a new observation with the same `block.timestamp`. All observations in the buffer could be from the same block, all at the manipulated price. The TWAP would reflect the manipulated price.

- **Impact:** TWAP oracle provides weak manipulation resistance for low-activity pools and is fully defeatable via same-block multi-swap attacks.
- **Recommendation:**
  - Only record one observation per block (skip if `timestamp == lastRecordedTimestamp`).
  - Require a minimum number of distinct-timestamp observations before `_checkTWAP` considers the TWAP valid.
  - Consider increasing the window or using a time-weighted accumulator (cumulative tick * time) instead of discrete samples.

### SE-v2-03: `_checkSlippage` compares sum of both token costs against single-token expected value

- **Severity:** MEDIUM
- **Category:** Math Issue
- **File:** `ILAlphaVault.sol:373-377`
- **Description:** `_checkSlippage` computes:
  ```
  actualCost = abs(d0) + abs(d1)   // sum of both token amounts consumed
  maxCost = expected + (expected * maxSlippageBps) / 10_000
  ```
  The `expected` parameter is `assets` (the total asset amount passed to `_executeAddLiquidity`). The problem:
  - `d0` and `d1` are denominated in different tokens (e.g., USDC and WETH).
  - Adding `uint128(-d0)` (USDC, 6 decimals) and `uint128(-d1)` (WETH, 18 decimals) produces a meaningless number.
  - For ETH/USDC at $3000: adding 1500e6 (USDC) + 0.5e18 (WETH) = 500000001500000000, which is dominated by the WETH amount due to its higher decimal precision.
  - The comparison against `expected` (which is in asset-token units) is therefore not a valid slippage check for heterogeneous-decimal pairs.

  **When it "works":** Only for same-decimal, same-value pairs (e.g., USDC/USDT).

- **Impact:** Slippage protection is ineffective for any pool where the two tokens have different decimals or different prices. Either always passes (if WETH decimals dominate and `expected` is in USDC) or always fails (vice versa).
- **Recommendation:** Check slippage per-token, comparing each delta against its expected contribution. Or convert both deltas to a common denomination (e.g., asset-token value using the pool price).

### SE-v2-04: `claimFees` with `min(fees, available)` can leave `accumulatedFees > 0` permanently

- **Severity:** LOW
- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:524-533`
- **Description:** The fix for SE-14 uses:
  ```solidity
  uint256 claimable = fees > available ? available : fees;
  accumulatedFees = fees - claimable;
  ```
  If `available < fees`, the owner claims `available` and `accumulatedFees` retains the residual (`fees - available`). This residual can never be claimed if:
  1. The vault is paused and no new deposits come in (balance stays at zero).
  2. The residual fees are "phantom" -- they were accumulated from withdrawal fees that reduced user payouts, but the corresponding tokens were already transferred out to users (net of fee). In that case, the residual `accumulatedFees` is a real debt owed by the vault but unfunded.

  **The more subtle issue:** `accumulatedFees` is incremented in `withdraw`/`redeem` but the fee tokens are NOT actually segregated -- they remain in `asset.balanceOf(address(this))`, which is also counted in `totalAssets()`. This means:
  - Fees inflate `totalAssets()`, giving existing share holders a higher apparent value.
  - When `claimFees()` transfers tokens out, `totalAssets()` drops, reducing share value for remaining holders.
  - The fees are effectively double-booked: counted as vault assets AND as owner-claimable fees.

- **Impact:** Share price includes unclaimed fees. Claiming fees reduces share price for remaining depositors. This is a value leak from depositors to the owner beyond the stated fee rate.
- **Recommendation:** Exclude `accumulatedFees` from `totalAssets()`:
  ```solidity
  function totalAssets() public view override returns (uint256) {
      uint256 idle = asset.balanceOf(address(this));
      uint256 netIdle = idle > accumulatedFees ? idle - accumulatedFees : 0;
      // ... add LP value to netIdle ...
  }
  ```

### SE-v2-05: `setMaxSlippageBps` has no event emission

- **Severity:** LOW
- **Category:** Missing Guardrail
- **File:** `ILAlphaVault.sol:513-516`
- **Description:** All other admin setters emit events: `DepositCapUpdated`, `TwapThresholdUpdated`, `WithdrawalFeeUpdated`, `KeeperUpdated`, `PauseUpdated`, `PoolKeyUpdated`. But `setMaxSlippageBps` does not emit any event. Off-chain monitoring and governance dashboards cannot detect slippage parameter changes.
- **Impact:** Reduced transparency. A compromised owner could silently set `maxSlippageBps = 500` (5%) to enable MEV extraction on rebalances without detection.
- **Recommendation:**
  ```solidity
  event MaxSlippageBpsUpdated(uint256 oldBps, uint256 newBps);

  function setMaxSlippageBps(uint256 _bps) external onlyOwner {
      require(_bps <= 500, "Max 5%");
      emit MaxSlippageBpsUpdated(maxSlippageBps, _bps);
      maxSlippageBps = _bps;
  }
  ```

### SE-v2-06: `getTwapTick` loop gas cost -- fixed 10 iterations, acceptable but fragile

- **Severity:** LOW
- **Category:** Gas / Design
- **File:** `ILAlphaHook.sol:459-481`
- **Description:** The loop iterates exactly 10 times (constant `TWAP_WINDOW = 10`). Each iteration reads from storage (`tickObservations[poolId][i]`), costing ~2100 gas for cold reads or ~100 gas for warm reads. Worst case: 10 cold SLOAD = ~21,000 gas. This function is called from:
  1. `_checkTWAP()` in `ILAlphaVault`, which is called from `deposit`, `mint`, `withdraw`, `redeem`.
  2. It is a `view` function, so on-chain calls pay gas but off-chain calls are free.

  **10 iterations at ~21K gas is acceptable.** The concern is that this runs on every user deposit/withdraw. Combined with the `totalAssets()` call (which also reads pool state), a single `deposit` incurs significant external call overhead.

  **The real issue:** `getTwapTick` is called via `hook.getTwapTick(poolId)` which is a cross-contract call. The entire function runs in the hook's context. If the hook is at a cold address, the initial `CALL` costs 2600 gas plus the loop. Total overhead per deposit/withdraw: ~25-30K gas for TWAP validation alone.

- **Impact:** Elevated gas costs for users. Not a vulnerability, but a UX consideration.
- **Recommendation:** Acceptable for current design. If gas becomes a concern, consider caching the TWAP result with a staleness threshold (e.g., recompute only if last computation was >12 seconds ago).

---

## Part 3: Additional New Sharp Edges

### SE-v2-07: `withdraw` overcharges shares -- fee is deducted from transfer but shares are burned for full `assets`

- **Severity:** HIGH
- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:329-347`
- **Description:** In the overridden `withdraw()`:
  ```solidity
  shares = previewWithdraw(assets);         // shares needed to withdraw `assets`
  // ... allowance check ...
  _burn(owner_, shares);                     // burn shares worth `assets`
  asset.safeTransfer(receiver, assets - fee); // send only `assets - fee`
  ```
  The user burns shares worth `assets` but only receives `assets - fee`. This is the intended fee mechanism. However, the ERC-4626 specification says `withdraw(assets)` should give the user exactly `assets` worth of tokens. The vault charges shares for `assets` but delivers `assets - fee`, breaking the ERC-4626 invariant.

  **User-facing impact:** A user calling `withdraw(1000e6)` expects 1000 USDC. They burn shares equivalent to 1000 USDC. They receive 999 USDC (0.1% fee). This is a deviation from the ERC-4626 standard. Integrators (aggregators, routers, other protocols) that rely on the standard may account incorrectly.

  **The `redeem` path has the same issue** but is arguably correct since `redeem` is share-denominated: burn `shares`, receive `previewRedeem(shares) - fee`.

- **Impact:** ERC-4626 compliance violation. Third-party integrations may misaccount.
- **Recommendation:** Either:
  (a) Burn shares for `assets + fee` (user pays more shares to receive exactly `assets`), or
  (b) Document the deviation explicitly and override `maxWithdraw` / `previewWithdraw` to account for the fee.

### SE-v2-08: `setMaxSlippageBps` allows zero -- disables slippage protection

- **Severity:** MEDIUM
- **Category:** Config Footgun
- **File:** `ILAlphaVault.sol:513-516`
- **Description:** `setMaxSlippageBps` only enforces `_bps <= 500`. Setting `_bps = 0` means `maxCost = expected + 0 = expected`. The slippage check becomes `actualCost > expected`, which is an exact match requirement. Given that `_checkSlippage` sums both token costs (see SE-v2-03), this will cause almost every LP addition to revert because the sum of two token amounts will rarely equal the single-token input exactly.

  Conversely, if SE-v2-03 is fixed and per-token slippage is used, setting `maxSlippageBps = 0` would require zero slippage, which is unrealistic for any AMM operation. Either way, `0` is a footgun value.

- **Impact:** Setting to 0 bricks LP rebalancing (all `_executeAddLiquidity` calls revert).
- **Recommendation:** Add `require(_bps >= 1, "Min 0.01%")` or `require(_bps >= 10, "Min 0.1%")`.

### SE-v2-09: `ILAlphaHook.setKeeper` has no event emission

- **Severity:** LOW
- **Category:** Missing Guardrail
- **File:** `ILAlphaHook.sol:498-501`
- **Description:** `ILAlphaVault.setKeeper` emits `KeeperUpdated`, but `ILAlphaHook.setKeeper` does not emit any event. Keeper changes on the hook are invisible to off-chain monitoring. The hook's keeper controls vol oracle updates and evaluation triggers -- silent changes here are higher risk than vault-side keeper changes.
- **Recommendation:** Add a `KeeperUpdated` event to `ILAlphaHook`.

### SE-v2-10: `setLPRange` has no event emission

- **Severity:** LOW
- **Category:** Missing Guardrail
- **File:** `ILAlphaHook.sol:409-417`
- **Description:** `setLPRange` modifies the LP tick range (directly affecting where the vault deploys capital) but emits no event. The `PoolRegistered` event fires on `afterInitialize` with the initial range, but subsequent range changes are silent.
- **Recommendation:** Emit an `LPRangeUpdated(PoolId indexed poolId, int24 tickLower, int24 tickUpper)` event.

### SE-v2-11: `setLambda` has no event emission

- **Severity:** LOW
- **Category:** Missing Guardrail
- **File:** `ILAlphaHook.sol:503-506`
- **Description:** `setLambda` changes the EWMA decay factor, directly affecting how the vol oracle responds to price changes. No event is emitted. A compromised owner could silently set `lambda = 9900` (very slow decay), making the oracle nearly unresponsive to new volatility, causing the vault to stay in LP during high-vol periods.
- **Recommendation:** Emit a `LambdaUpdated(PoolId indexed poolId, uint16 oldLambda, uint16 newLambda)` event.

### SE-v2-12: `_ensureIdle` removes ALL liquidity even if only a small shortfall

- **Severity:** MEDIUM
- **Category:** Design Misuse
- **File:** `ILAlphaVault.sol:380-385`
- **Description:** When a withdrawal needs more idle tokens than available:
  ```solidity
  function _ensureIdle(uint256 needed) internal {
      uint256 idle = asset.balanceOf(address(this));
      if (idle < needed && deployedLiquidity > 0) {
          _removeLiquidity();  // removes ALL deployed liquidity
      }
  }
  ```
  A small withdrawal that slightly exceeds idle balance triggers a full LP removal. For example, if the vault has 9,000 USDC idle and 1,000 USDC in LP, a withdrawal of 9,001 USDC removes all LP to satisfy the 1 USDC shortfall. After withdrawal, the vault has ~999 USDC idle and 0 LP.

  This has cascading effects:
  1. The next `rebalance()` must re-deploy, incurring gas and slippage.
  2. LP removal and re-addition both trigger pool state changes, potentially affecting the vol oracle.
  3. MEV bots can exploit the predictable full-removal pattern.

- **Impact:** Unnecessary LP churn, gas waste, and MEV exposure.
- **Recommendation:** Implement partial LP removal proportional to the shortfall.

### SE-v2-13: `PoolKeyUpdated` event has no parameters

- **Severity:** LOW
- **Category:** Missing Guardrail
- **File:** `ILAlphaVault.sol:67, 479-488`
- **Description:** The `PoolKeyUpdated` event is declared with no parameters: `event PoolKeyUpdated()`. When `setPoolKey` is called, off-chain consumers see that the pool key changed but cannot determine what it changed to without making an additional RPC call. All other setter events emit old and new values.
- **Note:** Looking at the code again, `setPoolKey` does not actually emit `PoolKeyUpdated`. The event is declared but never emitted.
- **Impact:** Pool key changes are completely invisible to off-chain monitoring.
- **Recommendation:** Emit `PoolKeyUpdated` in `setPoolKey` with relevant pool parameters.

---

## Part 4: Admin Setter Guardrail Audit

| Setter | Contract | Bounds Check | Event | Zero-Check | Notes |
|--------|----------|-------------|-------|------------|-------|
| `setTwapThreshold` | Vault | 10-2000 | Yes | N/A (int24) | OK |
| `setMaxSlippageBps` | Vault | <= 500 | **NO** | **No min** | Missing event, allows 0 (SE-v2-05, SE-v2-08) |
| `setWithdrawalFeeBps` | Vault | <= 100 | Yes | Allows 0 | 0 is valid (no fee), OK |
| `setDepositCap` | Vault | None | Yes | Allows 0 | 0 bricks deposits (SE-11, accepted) |
| `setKeeper` | Vault | N/A | Yes | Yes | OK |
| `setKeeper` | Hook | N/A | **NO** | Yes | Missing event (SE-v2-09) |
| `setPoolKey` | Vault | Asset check | **NO** (declared but not emitted) | N/A | Missing emission (SE-v2-13) |
| `setPaused` | Vault | N/A | Yes | N/A | OK |
| `setLPRange` | Hook | lower < upper, spacing | **NO** | N/A | Missing event (SE-v2-10) |
| `setLambda` | Hook | 5000-9900 | **NO** | N/A | Missing event (SE-v2-11) |
| `transferOwnership` | Both | N/A | Yes | Yes | OK (two-step) |

**Summary:** 4 of 10 admin setters lack event emissions. 1 setter (`setMaxSlippageBps`) lacks both a minimum bound and event.

---

## Part 5: Cross-Cutting Concerns (Updated)

### Accumulated Fees Double-Booking (NEW -- HIGH)

`accumulatedFees` is incremented during withdrawals, and those fee tokens remain in `asset.balanceOf(address(this))`. Since `totalAssets()` reads `asset.balanceOf(address(this))` for idle balance, the fees are counted as vault assets. This means:
- Share price includes unclaimed fees (inflated).
- When owner calls `claimFees`, `totalAssets()` drops, diluting remaining shareholders.
- In effect, depositors subsidize the fee claim -- they see their share value decrease by the fee amount.

This is the most significant new issue. See SE-v2-04 for details.

### Vol Oracle Noise (UNCHANGED)

SE-12 remains unfixed. The `3600 / elapsed` normalization still amplifies single-second tick changes by 3600x. In high-frequency trading environments, this creates systematic upward vol bias.

### Emergency Flow Gaps (UNCHANGED)

SE-15 remains: `emergencyWithdraw` does not reset `accumulatedFees`. Combined with the double-booking issue (SE-v2-04), post-emergency fee claims can drain residual user funds.

### Timelock (UNCHANGED)

No timelock on admin functions. All take effect immediately.

---

## Severity Summary (New Findings Only)

| ID | Severity | Finding |
|----|----------|---------|
| SE-v2-01 | LOW | `beforeWithdraw` is dead code after override |
| SE-v2-02 | MEDIUM | TWAP cold-start and same-block manipulation |
| SE-v2-03 | MEDIUM | `_checkSlippage` sums cross-denomination tokens |
| SE-v2-04 | HIGH | Accumulated fees double-booked in totalAssets |
| SE-v2-05 | LOW | `setMaxSlippageBps` missing event |
| SE-v2-06 | LOW | `getTwapTick` gas acceptable (~25K per call) |
| SE-v2-07 | HIGH | `withdraw` burns shares for full amount, sends less (ERC-4626 violation) |
| SE-v2-08 | MEDIUM | `setMaxSlippageBps(0)` bricks LP rebalancing |
| SE-v2-09 | LOW | `ILAlphaHook.setKeeper` missing event |
| SE-v2-10 | LOW | `setLPRange` missing event |
| SE-v2-11 | LOW | `setLambda` missing event |
| SE-v2-12 | MEDIUM | `_ensureIdle` removes all LP for small shortfall |
| SE-v2-13 | LOW | `PoolKeyUpdated` event declared but never emitted |

| Severity | Count |
|----------|-------|
| HIGH     | 2     |
| MEDIUM   | 4     |
| LOW      | 7     |

---

*End of sharp edges v2 re-audit.*
