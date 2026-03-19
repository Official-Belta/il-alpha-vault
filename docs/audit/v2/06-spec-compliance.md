# V2 Spec-to-Code Compliance Report

**Audit Type:** Post-fix compliance verification (v2)
**Date:** 2026-03-20
**Scope:** All 6 contracts in `contracts/src/`, verified against v1 report, NatSpec, ENG_COMPLETE.md
**Baseline:** `docs/audit/06-spec-compliance.md` (v1 report)

---

## Summary

| Category | Compliant | Non-Compliant | Partial | Notes |
|----------|-----------|---------------|---------|-------|
| v1 Critical fixes | 3 | 0 | 0 | All 3 resolved |
| v1 High fixes | 5 | 0 | 1 | AlwaysLPVault still simulation-only (documented) |
| v1 Medium fixes | 2 | 0 | 1 | TWAP improved but NatSpec slightly overstates |
| NatSpec accuracy (new) | 3 | 1 | 1 | See Section 3 |
| ERC-4626 compliance (new) | 3 | 2 | 1 | See Section 4 |

**New findings: 0 Critical | 1 High | 2 Medium | 1 Low | 1 Informational**

---

## 1. V1 Critical Findings — Re-verification

### 1.1 C-1 (v1 Finding 2.3/7.1): Withdrawal Fee Not Deducted

- **v1 Status:** NON-COMPLIANT (Critical)
- **v2 Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:329-347` (`withdraw`), `ILAlphaVault.sol:351-370` (`redeem`)
- **Verification:** Both `withdraw()` and `redeem()` are now fully overridden. Fee is computed as `(assets * withdrawalFeeBps) / 10_000`, accumulated in `accumulatedFees`, and the user receives `assets - fee` via `asset.safeTransfer(receiver, assets - fee)`. The fee is actually deducted from the transfer amount.
- **Residual issues:** See Section 4 for ERC-4626 event compliance concerns with this approach.

### 1.2 C-2 (v1 Finding 2.2): mint() Bypasses Guards

- **v1 Status:** NON-COMPLIANT (Critical)
- **v2 Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:184-196`
- **Verification:** `mint()` is now overridden with `whenNotPaused`, `nonReentrant`, `DepositTooSmall` check, `DepositCapExceeded` check, and `_checkTWAP()`. Guards are identical to `deposit()`.

### 1.3 C-3/C-4 (v1 implicit): setPoolKey and twapThreshold

- **v2 Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:479-488` (setPoolKey with `LPStillDeployed` guard), `ILAlphaVault.sol:506-511` (twapThreshold range `[10, 2000]`)
- **Verification:** `setPoolKey` reverts if `deployedLiquidity > 0`. `setTwapThreshold` enforces `10 <= threshold <= 2000` with custom error `TwapThresholdOutOfRange`.

---

## 2. V1 High Findings — Re-verification

### 2.1 H-1 (v1 Finding 1.9/5.3): TWAP Was Last-Tick Proxy

- **v1 Status:** PARTIAL (Medium — "TWAP" used last swap tick)
- **v2 Status:** COMPLIANT (with caveat)
- **Code reference:** `ILAlphaHook.sol:448-481` (tick observation buffer + `getTwapTick`), `ILAlphaVault.sol:414-430` (`_checkTWAP` uses `hook.getTwapTick`)
- **Verification:** A 10-observation circular buffer (`TWAP_WINDOW = 10`) records tick+timestamp on every swap. `getTwapTick()` computes a recency-weighted average: observations are weighted by `3600 - age` (newer = higher weight), and observations older than 1 hour are excluded. `_checkTWAP()` in the vault now calls `hook.getTwapTick(poolId)` instead of using raw `lastTick`.
- **Caveat:** This is technically a WMA (weighted moving average) by recency, not a strict TWAP (which weights by time-between-observations). The NatSpec `@notice Get time-weighted average tick` is reasonable but imprecise. The protection is significantly improved over v1's single-tick proxy.

### 2.2 H-2: Slippage Protection

- **v2 Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:373-377` (`_checkSlippage`), `ILAlphaVault.sol:91` (`maxSlippageBps = 100`)
- **Verification:** After `modifyLiquidity`, actual cost is compared against `expected + (expected * maxSlippageBps) / 10_000`. Reverts with `SlippageExceeded` if exceeded.

### 2.3 H-4 (v1 Finding 1.5/5.1): Rate Limit 2x vs 4x

- **v1 Status:** NON-COMPLIANT (Critical — code used `currentVar * 4`, NatSpec said 2x)
- **v2 Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:375-388`
- **Verification:** NatSpec says `max change per push is 2x current value` (line 375). Code uses `currentVar * 2` as `maxExternal` (line 385). With 50/50 blending: `(currentVar + 2*currentVar) / 2 = 1.5 * currentVar`. The raw external input is capped at 2x, and the effective blended result cannot exceed 1.5x current value. The NatSpec refers to the input cap (2x), which is accurate. The zero-baseline cap of `1e18` prevents unbounded initial push.

### 2.4 H-5 (v1 Finding 7.2): withdraw/redeem Missing nonReentrant

- **v1 Status:** NON-COMPLIANT (Medium)
- **v2 Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:330` (`withdraw ... nonReentrant`), `ILAlphaVault.sol:351` (`redeem ... nonReentrant`)
- **Verification:** Both overridden functions have `nonReentrant` modifier. Comment explicitly notes: "No whenNotPaused -- users must be able to withdraw after emergency". The asymmetry (deposits blocked when paused, withdrawals allowed) is now documented.

### 2.5 H-6 (v1 Finding 1.10/6.4): AlwaysLPVault Not Actually LPing

- **v1 Status:** NON-COMPLIANT (High — claimed to LP but didn't)
- **v2 Status:** PARTIAL (documented limitation)
- **Code reference:** `AlwaysLPVault.sol:9-11`
- **Verification:** NatSpec now says `@dev H-6 FIX: no deployedAssets tracking -- totalAssets = balance only. This is a simulation vault. It doesn't actually deploy to V4.` The double-count bug (stale `deployedAssets` added to balance) is fixed. However, AlwaysLPVault still does not provide actual LP, making it useless as a benchmark for real IL comparison. The NatSpec now honestly labels it a "simulation vault", which resolves the spec-to-code mismatch but not the product gap.
- **Risk:** Low (security). The misleading claim is fixed. Benchmark validity remains a product concern, not a code compliance issue.

### 2.6 H-7: totalAssets Counts Only Asset Token

- **v2 Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:149-168`
- **Verification:** `totalAssets()` calls `_getDeployedLPValue()` which returns `(amount0, amount1)`, then only adds the amount corresponding to the vault's asset currency. Cross-token valuation errors are avoided.

### 2.7 H-8: Admin Setter Events

- **v2 Status:** COMPLIANT
- **Code reference:** Events declared at lines 63-67, emitted in `setKeeper` (497), `setDepositCap` (502), `setTwapThreshold` (509), `setWithdrawalFeeBps` (520), `setPaused` (492).

---

## 3. NatSpec Comment Accuracy (New Checks)

### 3.1 "Rate limited: max change per push is 2x" — Does Code Match?

- **Status:** COMPLIANT
- **NatSpec:** `ILAlphaHook.sol:375` — `@dev Rate limited: max change per push is 2x current value (prevents keeper key abuse).`
- **Code:** `ILAlphaHook.sol:385` — `uint256 maxExternal = currentVar == 0 ? uint256(1e18) : currentVar * 2`
- **Assessment:** The external input is capped at 2x current value. After 50/50 blending, effective maximum result is 1.5x current value. The NatSpec correctly describes the input cap. The comment on line 383 (`H-4 FIX: rate limit to 2x (not 4x), cap zero baseline to 1e18`) accurately documents the change.

### 3.2 TWAP Comments — Does getTwapTick Compute Proper TWAP?

- **Status:** PARTIAL
- **Severity:** Low
- **NatSpec:** `ILAlphaHook.sol:457` — `@notice Get time-weighted average tick from recent observations`
- **Code:** `ILAlphaHook.sol:459-481`
- **Assessment:** The function computes a recency-weighted average, not a true TWAP. A TWAP weights each observation by the duration it was the current tick (time between consecutive observations). This implementation weights by `3600 - age` (linear decay from observation time). For practical oracle manipulation resistance this is adequate, but calling it "time-weighted average" is slightly misleading. More accurately described as "recency-weighted moving average tick".
- **Risk:** Low. The protection mechanism works (observations spread across time resist single-block manipulation). The naming is imprecise but not dangerous.

### 3.3 "H-3 NOTE: 50/50 split assumes vault holds both tokens. Phase 4: pre-swap."

- **Status:** COMPLIANT (documented as known limitation)
- **Code reference:** `ILAlphaVault.sol:280` — `@dev H-3 NOTE: 50/50 split assumes vault holds both tokens. Phase 4: pre-swap.`
- **Assessment:** The `_computeLiquidity` function splits `assets / 2` for both token amounts. This assumes the vault holds equal value of both tokens, which is generally false (vault holds only the deposit asset). The comment explicitly documents this as a known limitation deferred to Phase 4 (pre-swap before LP deployment). This is honest documentation of a design shortcoming.
- **Impact:** When the vault adds liquidity, it can only use half its assets (the half it can contribute as token0 or token1), wasting capital efficiency. No security risk — just reduced capital deployment.

---

## 4. ERC-4626 Compliance Re-check

### 4.1 Withdraw Event Accuracy

- **Status:** NON-COMPLIANT
- **Severity:** Medium
- **Spec reference:** ERC-4626 (EIP-4626) Section: "MUST emit the `Withdraw` event. ... `assets` ... the amount of assets being withdrawn"
- **Code reference:** `ILAlphaVault.sol:345` (`withdraw`), `ILAlphaVault.sol:368` (`redeem`)
- **Assessment:** Both functions emit `Withdraw(msg.sender, receiver, owner_, assets, shares)` where `assets` is the pre-fee gross amount. However, the user only receives `assets - fee`. Per ERC-4626, the `assets` parameter in the `Withdraw` event should represent the assets transferred to the receiver. Integrators (e.g., aggregators, portfolio trackers) relying on Withdraw events will see inflated withdrawal amounts.
  - `withdraw()`: User requests `assets`, event emits `assets`, user receives `assets - fee`.
  - `redeem()`: Preview gives `assets`, event emits `assets`, user receives `assets - fee`.
- **Recommendation:** Either emit `assets - fee` in the event (matching what user receives) or document the discrepancy clearly. The current approach breaks the ERC-4626 event contract.

### 4.2 Preview Functions Do Not Account for Fees

- **Status:** NON-COMPLIANT
- **Severity:** High
- **Spec reference:** ERC-4626 Section on `previewWithdraw`: "MUST return as close to and no fewer than the exact amount of Vault shares that would be burned in a withdraw call." And `previewRedeem`: "MUST return as close to and no more than the exact amount of assets that would be withdrawn in a redeem call."
- **Code reference:** `BaseVault.sol:44-52` — `previewWithdraw` and `previewRedeem` do not account for withdrawal fees
- **Assessment:**
  - `previewWithdraw(assets)` returns shares needed to withdraw `assets`. But the actual `withdraw()` function charges a fee, so the user must burn shares worth `assets` but only receives `assets - fee`. The preview is correct for shares burned but misleading for assets received.
  - `previewRedeem(shares)` returns the assets a user would get for `shares`. But actual `redeem()` deducts a fee, so the user receives less than `previewRedeem` promises. This directly violates ERC-4626: "MUST return as close to and no more than the exact amount of assets that would be withdrawn."
- **Impact:** Any integrator calling `previewRedeem(shares)` will believe the user gets X assets, but the user actually gets X minus fee. This breaks composability with routers, aggregators, and other vaults that depend on preview accuracy.
- **Recommendation:** Override `previewWithdraw` and `previewRedeem` to factor in `withdrawalFeeBps`. For example: `previewRedeem(shares)` should return `convertToAssets(shares) * (10_000 - withdrawalFeeBps) / 10_000`.

### 4.3 maxWithdraw / maxRedeem Do Not Account for Fees

- **Status:** PARTIAL
- **Severity:** Medium
- **Spec reference:** ERC-4626: `maxWithdraw` "MUST return the maximum amount of assets that could be transferred from owner through withdraw"
- **Code reference:** Inherited from solmate — `maxWithdraw(owner)` returns `convertToAssets(balanceOf[owner])`, `maxRedeem(owner)` returns `balanceOf[owner]`
- **Assessment:** `maxWithdraw` returns the gross asset amount, but the user will actually receive less due to fees. More importantly, if the vault's idle balance is insufficient to cover `maxWithdraw` and LP removal is needed, these functions don't account for potential slippage during LP removal. The fee discrepancy is the primary concern: a user calling `withdraw(maxWithdraw(user), ...)` will succeed but receive less than `maxWithdraw` implied.
- **Recommendation:** Override `maxWithdraw` to return the net-of-fee amount, or document that `maxWithdraw` returns gross (pre-fee) amounts.

### 4.4 maxMint Consistency

- **v1 Status:** PARTIAL (returned `type(uint256).max`)
- **v2 Status:** Still inherits solmate default (`type(uint256).max`)
- **Severity:** Low (unchanged from v1)
- **Assessment:** `maxDeposit` correctly returns `depositCap - totalAssets()`, but `maxMint` is not overridden to be consistent. This is a minor ERC-4626 spec violation.

### 4.5 deposit/mint Correctness

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:170-196`
- **Assessment:** Both `deposit()` and `mint()` have identical guards. `previewDeposit` and `previewMint` are accurate (no entry fee exists).

### 4.6 Withdraw Allowed While Paused

- **Status:** COMPLIANT (intentional design)
- **Code reference:** `ILAlphaVault.sol:328` — comment: "No whenNotPaused -- users must be able to withdraw after emergency"
- **Assessment:** This is now documented. Deposits are blocked when paused; withdrawals are allowed so users can exit after `emergencyWithdraw()`. This is a reasonable design choice.

---

## 5. New Compliance Issues from V2 Fixes

### 5.1 Withdraw Override: shares Computed but Allowance Check Duplicated

- **Status:** INFORMATIONAL
- **Code reference:** `ILAlphaVault.sol:339-346` (withdraw), `ILAlphaVault.sol:355-369` (redeem)
- **Assessment:** Both `withdraw()` and `redeem()` manually replicate solmate's allowance check, burn, and event emission instead of calling `super.withdraw()` / `super.redeem()`. This is necessary because the fee deduction changes the transfer amount. However, if solmate's ERC4626 implementation changes (e.g., in an upgrade), these overrides may become inconsistent. This is acceptable for a frozen codebase.

### 5.2 _ensureIdle May Leave Non-Asset Token Stranded

- **Status:** INFORMATIONAL (pre-existing, not introduced by v2)
- **Code reference:** `ILAlphaVault.sol:380-385`
- **Assessment:** When `_ensureIdle` triggers `_removeLiquidity()`, the LP position returns both tokens. The non-asset token remains in the vault with no mechanism to swap it back to the asset token. This is related to the H-3 known limitation (Phase 4: pre-swap). Not a new issue.

---

## 6. Cross-Reference with ENG_COMPLETE.md

| ENG_COMPLETE Claim | Verified | Notes |
|--------------------|----------|-------|
| C-1: withdraw/redeem fee deduction | YES | Fee deducted from transfer, accumulated correctly |
| C-2: mint() guards | YES | Identical guards to deposit() |
| C-3: setPoolKey LP guard | YES | Reverts with `LPStillDeployed` |
| C-4: twapThreshold range | YES | `[10, 2000]` enforced |
| H-1: Real TWAP (10-obs window) | YES | Recency-weighted, not strict TWAP (see 3.2) |
| H-2: Slippage protection | YES | `maxSlippageBps` checked post-modifyLiquidity |
| H-4: pushVol 2x + zero cap | YES | `currentVar * 2`, zero baseline `1e18` |
| H-5: withdraw/redeem nonReentrant | YES | Both have modifier |
| H-6: AlwaysLP double-count | YES | Removed `deployedAssets`, `totalAssets = balance` |
| H-7: totalAssets asset-only | YES | Only counts LP value in asset currency |
| H-8: Admin setter events | YES | All setters emit events |
| M-3: tick spacing alignment | YES | `tickLower % spacing == 0` checked |
| M-4: lower == upper prevention | YES | `if (lower >= upper) upper = lower + spacing` |
| L-4/L-5: zero-address checks | YES | `require != address(0)` on transferOwnership, setKeeper |
| L-6: claimFees balance check | YES | `claimable = min(fees, balance)` |
| H-3: Phase 4 pre-swap | DOCUMENTED | NatSpec note on `_computeLiquidity` (line 280) |

---

## 7. Risk Summary

### Resolved from V1

| ID | Description | v1 Severity | v2 Status |
|----|-------------|-------------|-----------|
| 1.5/5.1 | Rate limit 4x vs documented 2x | Critical | RESOLVED — now 2x |
| 2.2 | mint() bypasses all guards | Critical | RESOLVED — mint() overridden |
| 2.3/7.1 | Withdrawal fee phantom accounting | Critical | RESOLVED — fee deducted from transfer |
| 1.9/5.3 | TWAP uses last-tick proxy | Medium | RESOLVED — 10-obs weighted average |
| 7.2 | withdraw/redeem missing nonReentrant | Medium | RESOLVED — modifier added |
| 1.10/6.4 | AlwaysLPVault claims to LP | High | RESOLVED (documentation) — labeled "simulation vault" |

### New Findings (V2)

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| 4.2 | `previewRedeem` returns more assets than user actually receives (fee not reflected) | High | NON-COMPLIANT |
| 4.1 | `Withdraw` event emits pre-fee `assets`, not actual amount received | Medium | NON-COMPLIANT |
| 4.3 | `maxWithdraw` / `maxRedeem` return pre-fee amounts | Medium | PARTIAL |
| 3.2 | `getTwapTick` NatSpec says "TWAP" but implements recency-weighted average | Low | PARTIAL |
| 5.1 | Manual allowance/burn replication in withdraw/redeem overrides | Informational | Acceptable |

### Unchanged from V1 (not addressed, documented as future work)

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| 4.3 (v1) | Fee yield vs IL cost dimensional inconsistency | Medium | Known — heuristic, not rigorous |
| 1.6 (v1) | Variance tracked in tick-space, NatSpec says log-return | Low | Known |
| 4.5 (v1) | `getVolEstimate` returns variance labeled as "Vol" | Low | Known |
| 2.4 (v1) | `maxMint` returns `type(uint256).max` | Low | Known |

---

## 8. Recommendations

1. **Override `previewWithdraw` and `previewRedeem`** (High) to reflect withdrawal fees. This is required for ERC-4626 compliance and integrator safety. `previewRedeem(shares)` should return `convertToAssets(shares) * (10_000 - withdrawalFeeBps) / 10_000`.

2. **Fix Withdraw event emission** (Medium) to emit net assets (`assets - fee`) instead of gross assets, or document the convention explicitly for integrators.

3. **Override `maxWithdraw`** (Medium) to return net-of-fee amount: `convertToAssets(balanceOf[owner]) * (10_000 - withdrawalFeeBps) / 10_000`.

4. **Rename `getTwapTick` to `getWeightedAverageTick`** (Low) or update NatSpec to say "recency-weighted average" instead of "time-weighted average".
