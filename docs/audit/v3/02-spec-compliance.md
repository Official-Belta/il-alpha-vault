# V3 Spec-to-Code Compliance & ERC-4626 Conformance Report

**Audit Type:** V3 compliance verification — post-fee-removal
**Date:** 2026-03-20
**Scope:** `contracts/src/ILAlphaVault.sol`, `contracts/src/BaseVault.sol`
**Baseline:** `docs/audit/v2/06-spec-compliance.md` (V2 report)
**Model:** Claude Opus 4.6 (1M context)

---

## Summary

| Category | Compliant | Non-Compliant | Partial | Notes |
|----------|-----------|---------------|---------|-------|
| ERC-4626 core functions (9 checks) | 7 | 0 | 2 | maxDeposit/maxMint paused gap |
| V2 HIGH regressions | 0 | 0 | 0 | Fee removal resolved all V2 ERC-4626 HIGHs |
| NatSpec accuracy | 5 | 1 | 1 | PoolKeyUpdated event, TWAP naming |
| Events emitted | 9 | 1 | 0 | PoolKeyUpdated declared but never emitted |
| Errors used | 11 | 0 | 0 | All errors reachable (OnlyKeeper via dead modifier, see 5.1) |
| Dead code | — | — | — | 3 items found |

**New findings: 0 Critical | 0 High | 1 Medium | 3 Low | 2 Informational**

---

## 1. V2 HIGH Findings — Resolution Status

### 1.1 V2-4.2 (HIGH): previewRedeem Returns More Than Actual (Fee Mismatch)

- **V2 Status:** NON-COMPLIANT (High)
- **V3 Status:** RESOLVED
- **Verification:** V3 removed all fee logic (`withdrawalFeeBps`, `accumulatedFees`, `claimFees` — all absent from codebase). `withdraw()` and `redeem()` now delegate to `super.withdraw()` / `super.redeem()` (solmate ERC4626), which transfer exactly `assets` to receiver. `previewRedeem(shares)` returns `convertToAssets(shares)`, which equals the actual transfer amount. No fee distortion exists.

### 1.2 V2-4.1 (Medium): Withdraw Event Emits Pre-Fee Amount

- **V2 Status:** NON-COMPLIANT (Medium)
- **V3 Status:** RESOLVED
- **Verification:** With no fees, `Withdraw` event `assets` parameter equals the amount transferred to receiver. Solmate's base implementation emits the event at line 90/113 of `ERC4626.sol` with the same `assets` value passed to `safeTransfer`.

### 1.3 V2-4.3 (Medium): maxWithdraw/maxRedeem Pre-Fee Amounts

- **V2 Status:** PARTIAL (Medium)
- **V3 Status:** RESOLVED
- **Verification:** With no fees, `maxWithdraw(owner) = convertToAssets(balanceOf[owner])` and `maxRedeem(owner) = balanceOf[owner]` are now accurate. The user receives exactly what these functions predict.

---

## 2. ERC-4626 Full Compliance Check

### 2.1 `deposit(assets, receiver)` — Transfers Exactly `assets`, Mints Shares

- **Status:** COMPLIANT
- **Code path:** `ILAlphaVault.deposit()` (line 164) → guards → `super.deposit()` → solmate `ERC4626.deposit()` (line 46)
- **Verification:** Solmate calls `asset.safeTransferFrom(msg.sender, address(this), assets)` then `_mint(receiver, shares)` where `shares = previewDeposit(assets)`. The vault adds `whenNotPaused`, `nonReentrant`, `DepositTooSmall`, `DepositCapExceeded`, and `_checkTWAP()` guards before delegating.
- **Event:** `Deposit(msg.sender, receiver, assets, shares)` emitted by solmate. Correct.

### 2.2 `mint(shares, receiver)` — Transfers Required Assets, Mints Exactly `shares`

- **Status:** COMPLIANT
- **Code path:** `ILAlphaVault.mint()` (line 178) → guards → `super.mint()` → solmate `ERC4626.mint()` (line 60)
- **Verification:** Solmate computes `assets = previewMint(shares)` (rounds up), calls `safeTransferFrom(msg.sender, ..., assets)`, mints exactly `shares`. Guards mirror `deposit()`.
- **Note:** `ILAlphaVault.mint()` computes `assets = previewMint(shares)` at line 185 for the `DepositTooSmall` and `DepositCapExceeded` checks, then calls `super.mint(shares, receiver)` which recomputes `previewMint(shares)`. This is a redundant computation but not incorrect — both calls see the same state so the result is identical.
- **Event:** `Deposit(msg.sender, receiver, assets, shares)` emitted by solmate. Correct.

### 2.3 `withdraw(assets, receiver, owner)` — Burns Shares, Transfers Exactly `assets`

- **Status:** COMPLIANT
- **Code path:** `ILAlphaVault.withdraw()` (line 327) → `_checkTWAP()` → `super.withdraw()` → solmate `ERC4626.withdraw()` (line 73)
- **Verification:** Solmate computes `shares = previewWithdraw(assets)`, handles allowance, calls `beforeWithdraw(assets, shares)` (which triggers LP removal if needed), burns `shares`, emits `Withdraw`, transfers exactly `assets` via `safeTransfer(receiver, assets)`.
- **Event:** `Withdraw(msg.sender, receiver, owner, assets, shares)` emitted by solmate. Correct.

### 2.4 `redeem(shares, receiver, owner)` — Burns Exactly `shares`, Transfers Assets

- **Status:** COMPLIANT
- **Code path:** `ILAlphaVault.redeem()` (line 334) → `_checkTWAP()` → `super.redeem()` → solmate `ERC4626.redeem()` (line 95)
- **Verification:** Solmate handles allowance, computes `assets = previewRedeem(shares)`, calls `beforeWithdraw`, burns exactly `shares`, emits `Withdraw`, transfers `assets`. Requires `assets != 0`.
- **Event:** `Withdraw(msg.sender, receiver, owner, assets, shares)` emitted by solmate. Correct.

### 2.5 Preview Functions — Accurate Predictions

- **Status:** COMPLIANT
- **Code reference:** `BaseVault.sol:34-52`
- **Verification (no fees, all preview = actual):**

| Function | Formula | Rounding | Matches Actual? |
|----------|---------|----------|-----------------|
| `previewDeposit(assets)` | `convertToShares(assets)` = `assets * (supply + 1e6) / (total + 1e6)` | Down | YES — `deposit` uses same path |
| `previewMint(shares)` | `shares * (total + 1e6) / (supply + 1e6)` | Up | YES — `mint` uses same, rounds up (caller pays more) |
| `previewWithdraw(assets)` | `assets * (supply + 1e6) / (total + 1e6)` | Up | YES — `withdraw` uses same, rounds up (burns more shares) |
| `previewRedeem(shares)` | `convertToAssets(shares)` = `shares * (total + 1e6) / (supply + 1e6)` | Down | YES — `redeem` uses same path |

- **Rounding direction:** Correct per ERC-4626 — deposit/redeem round down (favors vault), mint/withdraw round up (favors vault). Both directions protect the vault from rounding exploits.

### 2.6 `maxDeposit` / `maxMint` — Correct Limits

- **Status:** PARTIAL
- **Severity:** Medium (M-1)
- **Code reference:** `ILAlphaVault.sol:193-195` (`maxDeposit`), inherited solmate (`maxMint`)

**`maxDeposit`:**
- Returns `depositCap - totalAssets()` (or 0 if at cap). Correctly reflects the deposit cap.
- **Issue:** Does not return 0 when `paused == true`. Per ERC-4626: "MUST return 0 if deposits would revert." Since `deposit()` has `whenNotPaused` and will revert when paused, `maxDeposit` must return 0 during pause. An integrator calling `maxDeposit` to check if deposits are possible will get a nonzero value, then have the actual `deposit` revert.

**`maxMint`:**
- Inherits solmate default: `type(uint256).max`. Not overridden.
- **Issue 1:** Does not reflect the deposit cap. A caller could compute a mint amount from `maxMint` that exceeds the deposit cap, causing the actual `mint()` to revert.
- **Issue 2:** Does not return 0 when paused.
- **Recommendation:** Override `maxMint` to return `convertToShares(maxDeposit(address(0)))` (or 0 when paused).

### 2.7 `maxWithdraw` / `maxRedeem` — Correct Limits

- **Status:** COMPLIANT
- **Code reference:** Inherited from solmate `ERC4626.sol:168-174`
- **Verification:** `maxWithdraw(owner) = convertToAssets(balanceOf[owner])`, `maxRedeem(owner) = balanceOf[owner]`. With no fees, these match actual execution. `withdraw` and `redeem` are allowed even when paused (intentional design — users can always exit), so the max functions correctly do not return 0 when paused.
- **Caveat:** If LP removal during withdrawal triggers slippage that exceeds `maxSlippageBps`... no — slippage check is only on `_addLiquidity` (line 268), not on `_executeRemoveLiquidity` (line 319 comment: intentionally skipped). So withdrawal will not revert from slippage. TWAP check could cause revert, but this is a transient market condition, not a permanent limit — acceptable per ERC-4626 spec which says "MUST factor in... global and per-user limitations."

### 2.8 `convertToShares` / `convertToAssets` — Virtual Shares Offset

- **Status:** COMPLIANT
- **Code reference:** `BaseVault.sol:22-32`
- **Verification:** Both functions use `VIRTUAL_SHARES = 1e6` and `VIRTUAL_ASSETS = 1e6` offsets:
  - `convertToShares(assets) = assets * (totalSupply + 1e6) / (totalAssets() + 1e6)` — rounds down
  - `convertToAssets(shares) = shares * (totalAssets() + 1e6) / (totalSupply + 1e6)` — rounds down
- The virtual offset prevents the inflation attack (first depositor donates to inflate share price). With `1e6` offset and USDC (6 decimals), the minimum meaningful deposit cost to attack is ~$1, making inflation attacks economically impractical.
- **Spec note:** ERC-4626 says these functions "MUST NOT be inclusive of any fees." With fees removed, this is trivially satisfied.

### 2.9 `totalAssets()` — Accurate, No Phantom Fees, No Double-Counting

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaVault.sol:146-162`
- **Verification:** Returns `idle + lpValueInAssetToken` where:
  - `idle = asset.balanceOf(address(this))` — actual vault balance
  - LP value computed via `LiquidityAmounts.getAmountsForLiquidity()` using live `sqrtPriceX96` — not stale
  - H-7 fix: only counts LP value in the vault's asset currency, excluding the non-asset token
  - No phantom fees (fee code fully removed)
  - No double-counting: idle balance is from ERC20.balanceOf, LP value is from pool state — no overlap since tokens sent to the pool are no longer in the vault's balance

---

## 3. Events Audit

### 3.1 Declared Events vs Emission

| Event | Declared (line) | Emitted (line) | Status |
|-------|-----------------|----------------|--------|
| `Rebalanced` | 52-58 | 222 | COMPLIANT |
| `EmergencyWithdraw` | 59 | 489 | COMPLIANT |
| `OwnershipTransferStarted` | 60 | 432 | COMPLIANT |
| `OwnershipTransferred` | 61 | 437 | COMPLIANT |
| `KeeperUpdated` | 62 | 460 | COMPLIANT |
| `DepositCapUpdated` | 63 | 465 | COMPLIANT |
| `TwapThresholdUpdated` | 64 | 472 | COMPLIANT |
| `SlippageUpdated` | 65 | 479 | COMPLIANT |
| `PoolKeyUpdated` | 66 | — | **NON-COMPLIANT (L-1)** |
| `PauseUpdated` | 67 | 455 | COMPLIANT |
| `Deposit` (ERC-4626) | solmate | solmate (via super) | COMPLIANT |
| `Withdraw` (ERC-4626) | solmate | solmate (via super) | COMPLIANT |

### L-1: `PoolKeyUpdated` Event Declared But Never Emitted

- **Severity:** Low
- **Code reference:** Declared at line 66, `setPoolKey()` at lines 442-451 does not emit it.
- **Impact:** Off-chain monitoring cannot detect pool key changes. This is an admin function with significant operational impact (changes which pool the vault operates on).
- **Recommendation:** Add `emit PoolKeyUpdated();` at the end of `setPoolKey()`.

---

## 4. Errors Audit

### 4.1 Declared Errors vs Usage

| Error | Declared (line) | Used (line) | Status |
|-------|-----------------|-------------|--------|
| `OnlyOwner` | 38 | 116, 436 | COMPLIANT |
| `OnlyKeeper` | 39 | 126 | See 5.1 (dead code) |
| `OnlyPoolManager` | 40 | 239 | COMPLIANT |
| `Paused` | 41 | 121 | COMPLIANT |
| `DepositTooSmall` | 42 | 171, 186 | COMPLIANT |
| `DepositCapExceeded` | 43 | 172, 187 | COMPLIANT |
| `Reentrancy` | 44 | 131 | COMPLIANT |
| `InvalidPoolKey` | 45 | 449 | COMPLIANT |
| `PriceManipulated` | 46 | 392 | COMPLIANT |
| `LPStillDeployed` | 47 | 444 | COMPLIANT |
| `TwapThresholdOutOfRange` | 48 | 471 | COMPLIANT |
| `SlippageExceeded` | 49 | 352 | COMPLIANT |

All 12 declared errors are reachable. `OnlyKeeper` is technically reachable through the `onlyKeeper` modifier, but that modifier is never applied to any function (see Section 5.1).

---

## 5. Dead Code Analysis

### 5.1 I-1: `onlyKeeper` Modifier and `OnlyKeeper` Error — Dead Code

- **Severity:** Informational
- **Code reference:** `onlyKeeper` modifier (lines 125-128), `OnlyKeeper` error (line 39), `keeper` state variable (line 80), `setKeeper()` (lines 458-461), `KeeperUpdated` event (line 62)
- **Assessment:** `rebalance()` at line 203 is public with no access restriction — the `onlyKeeper` modifier is never applied. The `keeper` variable is set but never read in any access check. The entire keeper infrastructure (`keeper`, `setKeeper`, `onlyKeeper`, `OnlyKeeper`, `KeeperUpdated`) is vestigial. The NatSpec on `rebalance()` (line 201-202) correctly documents it as public: "Public — anyone can call."
- **Impact:** No security risk. Wasted bytecode and storage slot. The `setKeeper` function lets the owner set a `keeper` address that has no privileges.
- **Recommendation:** Either remove the keeper infrastructure entirely, or apply `onlyKeeper` to `rebalance()` if keeper-restricted access is intended.

### 5.2 I-2: Unused LP Value Computation in `_executeRemoveLiquidity`

- **Severity:** Informational
- **Code reference:** Lines 318-320
- **Assessment:** `_getDeployedLPValue()` is called and returns `(estValue0, estValue1)`, but neither value is used. The comment explains slippage checking was intentionally skipped on removal. However, the function call still executes, consuming gas for `getSlot0` + `getPoolStrategy` + `getAmountsForLiquidity` — all view calls but still costly in a state-changing context.
- **Furthermore:** This call happens *after* `_settleDelta(delta)` has already settled the removal. At this point `deployedLiquidity` is still nonzero but the position has been removed from the pool, so `_getDeployedLPValue()` would compute values based on stale `deployedLiquidity` against the post-removal pool state. The values would be meaningless even if they were used.
- **Recommendation:** Remove the dead call: delete lines 316-320.

### 5.3 L-2: Stale Comment — "fee deferred post-audit"

- **Severity:** Low
- **Code reference:** Line 324 — `// ─── Withdraw (H-5: reentrancy, no fee — fee deferred post-audit) ──`
- **Assessment:** V3 has explicitly removed fees. The comment "fee deferred post-audit" implies fees will be added later, which is misleading if fees were intentionally removed. Should be updated to reflect the current design intent.

---

## 6. NatSpec Accuracy

### 6.1 Contract-Level NatSpec

- **Status:** COMPLIANT
- **Code reference:** Lines 19-29
- **Assessment:** Accurately describes the vault as ERC-4626, mentions deposit flow, rebalance flow, and withdraw flow. The mention of "virtual shares (1e6 offset)" matches `BaseVault.VIRTUAL_SHARES`.

### 6.2 `totalAssets()` NatSpec

- **Status:** COMPLIANT
- **Code reference:** Lines 139-145
- **Assessment:** "Total assets = idle balance + real-time LP value" is accurate. References the Gamma hack (Jan 2024) for context on why live valuation matters. The H-7 FIX comment about excluding non-asset token value is accurate.

### 6.3 `_computeLiquidity` H-3 NOTE

- **Status:** COMPLIANT (documented limitation)
- **Code reference:** Line 274 — `@dev H-3 NOTE: 50/50 split assumes vault holds both tokens. Phase 4: pre-swap.`
- **Assessment:** The code does `assets / 2, assets / 2` (line 284). The comment honestly documents this as a known limitation.

### 6.4 TWAP Dedup Comment

- **Status:** COMPLIANT
- **Code reference:** `ILAlphaHook.sol:449` — `R-3 FIX: one observation per block (prevents same-block buffer flooding)`
- **Assessment:** The code checks `tickObservations[poolId][prevIdx].timestamp == uint40(block.timestamp)`. Since `block.timestamp` is identical for all transactions in a block, this correctly limits to one observation per block. The comment is accurate.
- **Note:** The dedup compares against the *previous* observation index's timestamp, which is the most recently written observation. This is correct — if the last write was in this block, skip.

### 6.5 TWAP Naming

- **Status:** PARTIAL (carried from V2)
- **Severity:** Low (L-3, carried from V2-3.2)
- **Code reference:** `ILAlphaHook.sol:461` — `@notice Get time-weighted average tick from recent observations`
- **Assessment:** The function computes a recency-weighted average (`weight = 3600 - age`), not a true TWAP. This was noted in the V2 audit (V2-3.2). The name `getTwapTick` and NatSpec "time-weighted average" remain slightly imprecise. Practically adequate for manipulation resistance, but technically the weighting scheme is inverse-age-linear, not time-between-observations.

### 6.6 `rebalance()` NatSpec

- **Status:** COMPLIANT
- **Code reference:** Lines 200-202
- **Assessment:** "Public — anyone can call. Result is deterministic (hook signal only). Keeper liveness is not a single point of failure." Matches the code: no access modifier, behavior depends only on `hook.isLPActive(poolKey)`.

---

## 7. M-1: `maxDeposit` / `maxMint` Do Not Return 0 When Paused

- **Severity:** Medium
- **Spec reference:** ERC-4626: "MUST return 0 if deposits would revert for all callers"
- **Code reference:** `ILAlphaVault.sol:193-195` (`maxDeposit`), solmate inherited (`maxMint`)

**`maxDeposit` issue:**
When `paused == true`, `deposit()` will unconditionally revert via `whenNotPaused`. However, `maxDeposit()` still returns `depositCap - totalAssets()`. Per ERC-4626 spec, it must return 0 when deposits would revert.

**`maxMint` issue:**
Inherits solmate's `type(uint256).max`. Does not reflect the deposit cap or paused state. `mint()` applies `whenNotPaused`, `DepositTooSmall`, and `DepositCapExceeded` — all of which can cause revert, yet `maxMint` does not account for any of them.

**Impact:** Integrators (routers, aggregators, yield optimizers) relying on `maxDeposit`/`maxMint` to determine deposit feasibility will receive incorrect values during pause or near the deposit cap. Transactions will revert unexpectedly.

**Recommendation:**
```solidity
function maxDeposit(address) public view override returns (uint256) {
    if (paused) return 0;
    uint256 total = totalAssets();
    if (total >= depositCap) return 0;
    uint256 remaining = depositCap - total;
    // Enforce minimum deposit size
    return remaining < VIRTUAL_ASSETS ? 0 : remaining;
}

function maxMint(address) public view override returns (uint256) {
    uint256 maxAssets = maxDeposit(address(0));
    return maxAssets == 0 ? 0 : convertToShares(maxAssets);
}
```

---

## 8. Risk Summary

### V2 Issues Resolved by Fee Removal

| V2 ID | Description | V2 Severity | V3 Status |
|-------|-------------|-------------|-----------|
| 4.2 | `previewRedeem` returns more than actual (fee mismatch) | High | RESOLVED — fees removed |
| 4.1 | `Withdraw` event emits pre-fee amount | Medium | RESOLVED — no fee distortion |
| 4.3 | `maxWithdraw`/`maxRedeem` return pre-fee amounts | Medium | RESOLVED — no fees |

### New V3 Findings

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| M-1 | `maxDeposit` does not return 0 when paused; `maxMint` not overridden | Medium | NON-COMPLIANT |
| L-1 | `PoolKeyUpdated` event declared but never emitted in `setPoolKey()` | Low | NON-COMPLIANT |
| L-2 | Stale comment "fee deferred post-audit" on line 324 | Low | STALE |
| L-3 | `getTwapTick` NatSpec says "TWAP" but implements recency-weighted average (carried from V2-3.2) | Low | PARTIAL |
| I-1 | `onlyKeeper` modifier, `keeper` variable, `setKeeper()`, `KeeperUpdated` event — all dead code; `rebalance()` is public | Informational | DEAD CODE |
| I-2 | `_executeRemoveLiquidity` calls `_getDeployedLPValue()` but discards results (lines 318-320) | Informational | DEAD CODE |

### Carried from V2 (Unchanged, Documented)

| V2 ID | Description | Severity | Status |
|-------|-------------|----------|--------|
| 4.4 (v1 2.4) | `maxMint` returns `type(uint256).max` | Low → now Medium (subsumed by M-1) | Escalated |
| 3.2 | `getTwapTick` naming imprecision | Low | Carried as L-3 |

---

## 9. ERC-4626 Compliance Matrix

| Function | Spec Requirement | V3 Status | Notes |
|----------|-----------------|-----------|-------|
| `deposit` | Transfer exactly `assets`, mint shares, emit `Deposit` | PASS | |
| `mint` | Transfer required assets, mint exactly `shares`, emit `Deposit` | PASS | |
| `withdraw` | Burn shares, transfer exactly `assets`, emit `Withdraw` | PASS | |
| `redeem` | Burn exactly `shares`, transfer assets, emit `Withdraw` | PASS | |
| `previewDeposit` | Match actual deposit (round down) | PASS | |
| `previewMint` | Match actual mint (round up) | PASS | |
| `previewWithdraw` | Match actual withdraw (round up) | PASS | |
| `previewRedeem` | Match actual redeem (round down) | PASS | |
| `maxDeposit` | Return 0 if deposit would revert | **FAIL** | Does not account for paused state |
| `maxMint` | Return 0 if mint would revert | **FAIL** | Not overridden; ignores cap and paused |
| `maxWithdraw` | Correct maximum withdrawable | PASS | |
| `maxRedeem` | Correct maximum redeemable | PASS | |
| `convertToShares` | Accurate, fee-exclusive | PASS | Virtual offset correct |
| `convertToAssets` | Accurate, fee-exclusive | PASS | Virtual offset correct |
| `totalAssets` | Accurate total managed assets | PASS | Live LP valuation, no phantom values |
| `Deposit` event | Correct parameters | PASS | Emitted by solmate base |
| `Withdraw` event | Correct parameters | PASS | Emitted by solmate base |

**Overall ERC-4626 compliance: 15/17 checks pass.** The two failures (`maxDeposit`, `maxMint`) are Medium severity — they affect integrator compatibility but not direct fund safety.

---

## 10. Recommendations (Priority Order)

1. **Override `maxDeposit` to return 0 when paused** (Medium — M-1). Override `maxMint` to reflect deposit cap and paused state.

2. **Emit `PoolKeyUpdated` in `setPoolKey()`** (Low — L-1). Admin state changes should be observable off-chain.

3. **Remove dead `_getDeployedLPValue()` call in `_executeRemoveLiquidity`** (Informational — I-2). Saves gas and removes confusion.

4. **Remove or apply `onlyKeeper` modifier** (Informational — I-1). Either restrict `rebalance()` to keepers or remove the entire keeper infrastructure.

5. **Update stale fee comment on line 324** (Low — L-2). Replace "fee deferred post-audit" with accurate description.

6. **Rename `getTwapTick` or update NatSpec** (Low — L-3). Use "recency-weighted average" instead of "time-weighted average".
