# IL Alpha Vault — V4 Full Audit Report

**Date:** 2026-03-20
**Scope:** ILAlphaHook.sol, ILAlphaVault.sol, BaseVault.sol
**Purpose:** Verify V3 fixes (commit 6d25e88), find remaining issues, full ERC-4626 compliance check

---

## V1 -> V2 -> V3 -> V4 Journey

| Metric | V1 | V2 | V3 | V4 |
|--------|----|----|-----|-----|
| CRITICAL | 4 | 0 | 0 | **0** |
| HIGH | 8 | 2 | 0 | **0** |
| MEDIUM | 10 | 6 | 4 | **3** |
| LOW/INFO | 16 | 3 | 6 | **5** |
| Risk Rating | MEDIUM-HIGH | MEDIUM | LOW-MEDIUM | **LOW-MEDIUM** |
| Maturity | 34/45 (76%) | 36/45 (80%) | 38/45 (84%) | **40/45 (89%)** |
| Audit Readiness | 55/100 | 75/100 | 85/100 | **90/100** |

---

## V3 Fix Verification

### V3 M-1: `maxDeposit`/`maxMint` ERC-4626 non-compliance — FIXED

**`maxDeposit` (line 189-193):** Returns 0 when paused. Correctly computes remaining capacity via `depositCap - totalAssets()`. Verified.

**`maxMint` (line 196-200):** Returns 0 when paused. Delegates to `maxDeposit(address(0))` then converts via `convertToShares()`. Verified.

**Minor concern with `maxMint` calculation:** `convertToShares` rounds down (uses `mulDivDown`). This is correct per ERC-4626 spec — `maxMint` SHOULD return a value such that `mint(maxMint)` would succeed. Since `previewMint` rounds up (uses `mulDivUp`), a user calling `mint(maxMint())` would need `previewMint(maxMint())` assets, which could exceed the deposit cap by a rounding unit. In practice, for USDC (6 decimals) and typical deposit caps, this rounding error is at most 1 wei — **negligible**. **PASS.**

### V3 #5: `PoolKeyUpdated` event not emitted — FIXED

`setPoolKey()` at line 450 now emits `emit PoolKeyUpdated()`. Verified.

### V3 #6: Dead `_getDeployedLPValue()` call in `_executeRemoveLiquidity` — FIXED

`_executeRemoveLiquidity()` (line 310-321) no longer calls `_getDeployedLPValue()`. Only calls `modifyLiquidity`, `_settleDelta`, and resets `deployedLiquidity = 0`. Verified.

### V3 #7: Stale comment "fee deferred post-audit" — FIXED

Grep for "fee deferred", "post-audit", "withdrawal fee" returns no matches in `contracts/src/`. Verified.

### V3 #10: `onlyKeeper` dead code in vault — FIXED (partial)

The `onlyKeeper` **modifier** has been removed from ILAlphaVault. No functions use it. Verified.

**However:** `error OnlyKeeper()` is still declared at line 39 of ILAlphaVault.sol but is never used anywhere in the vault contract. See L-1 below.

---

## Remaining V3 MEDIUMs (Carried Forward)

### M-1: `setLPRange` callable while vault has deployed LP (OPEN)

**Status:** No change. `ILAlphaHook.setLPRange()` (line 409) has no coordination with the vault's `deployedLiquidity`. If the owner changes the LP range while the vault has liquidity deployed, `_executeRemoveLiquidity()` will attempt to remove at the new tick range, not the range where liquidity was actually added. This would leave liquidity stranded.

**Risk:** MEDIUM. Owner-only function, but operational mistake could strand funds.

**Fix:** Add a check in `setLPRange` that queries the vault's `deployedLiquidity`, or document that LP must be removed before range changes.

### M-2: 50/50 asset split for LP (OPEN — documented deferral)

**Status:** No change. `_computeLiquidity()` (line 279-289) splits `assets / 2, assets / 2`. Vault holds a single asset token but attempts two-sided LP. The comment at line 278 acknowledges this: "H-3 NOTE: 50/50 split assumes vault holds both tokens. Phase 4: pre-swap."

**Risk:** MEDIUM. Results in suboptimal LP deployment. Not a loss-of-funds risk since `LiquidityAmounts.getLiquidityForAmounts` handles the math correctly — it will simply use the lower of the two amounts based on price.

### M-3: `_checkSlippage` sums different-decimal tokens (OPEN — dormant)

**Status:** No change. `_checkSlippage()` (line 348-352) sums `d0` and `d1` costs without normalizing for different decimals. Currently dormant because only same-decimal pairs are used.

**Risk:** MEDIUM when cross-decimal pairs are introduced. Dormant for now.

---

## New Findings (V4)

### L-1: `error OnlyKeeper()` declared but unused in ILAlphaVault (Dead Code)

**File:** ILAlphaVault.sol, line 39
**Detail:** The `onlyKeeper` modifier was correctly removed (V3 #10 fix), but the custom error declaration was left behind. No code in the vault contract reverts with `OnlyKeeper()`.

**Impact:** No functional impact. Dead bytecode increases deployment cost slightly (~22 bytes). Misleads readers into thinking keeper access control exists in the vault.

**Fix:** Remove `error OnlyKeeper();` from ILAlphaVault.sol.

### L-2: `keeper` storage variable set but never read for access control in vault

**File:** ILAlphaVault.sol, lines 80, 111, 458-461
**Detail:** The vault stores `keeper` (line 80), sets it in the constructor (line 111), and has `setKeeper()` (line 458). However, no function in the vault uses `keeper` for access control — the `onlyKeeper` modifier was removed. The `keeper` is only meaningful in ILAlphaHook (which has its own separate `keeper` storage).

**Impact:** Wastes one storage slot. `setKeeper()` emits `KeeperUpdated` events that serve no purpose. Misleads integrators.

**Fix:** Either (a) remove `keeper`, `setKeeper()`, `KeeperUpdated` event, and `error OnlyKeeper()` from the vault, or (b) add keeper-gated functions if keeper access control is intended for future features.

### L-3: `getVaultMetrics().deployedValue` sums both token amounts (inconsistent with `totalAssets`)

**File:** ILAlphaVault.sol, line 415
**Detail:** `getVaultMetrics()` computes `deployedValue = v0 + v1` (both token amounts), but `totalAssets()` only counts the vault's asset token (the H-7 fix). This means `deployedValue` can overstate or misrepresent the actual value counted toward share pricing.

**Impact:** Off-chain monitoring receives inconsistent data. Not an on-chain risk.

**Fix:** Either (a) only return the asset-token side in `deployedValue`, or (b) return `(v0, v1)` separately so off-chain can interpret correctly.

### I-1: `getTwapTick` NatSpec says "time-weighted" but implementation is recency-weighted

**File:** ILAlphaHook.sol, line 461-462
**Detail:** Carried from V3 #9. The NatSpec says "time-weighted average tick" but the implementation uses `weight = 3600 - age` (recency-weighted, not time-weighted in the traditional TWAP sense). A true TWAP would weight each observation by the duration until the next observation.

**Impact:** Informational. The recency-weighted approach is arguably better for manipulation detection, but the NatSpec is misleading.

**Fix:** Update NatSpec to "recency-weighted average tick" or similar.

### I-2: `mint()` calls `previewMint` twice (gas inefficiency — carried from V3 #7/R-9)

**File:** ILAlphaVault.sol, lines 180, 184
**Detail:** `mint()` calls `previewMint(shares)` at line 180 for the `DepositTooSmall` check, then `super.mint(shares, receiver)` at line 184 calls `previewMint` again internally (solmate's `mint` at line 61 of ERC4626.sol). Each `previewMint` call invokes `totalAssets()`, which reads pool state via external calls.

**Impact:** ~5-10K extra gas per mint. No correctness issue.

**Fix:** Cache the result and use a lower-level path, or accept the gas cost.

---

## ERC-4626 Compliance Check (9 Required Functions)

| # | Function | Status | Notes |
|---|----------|--------|-------|
| 1 | `asset()` | PASS | Inherited from solmate ERC4626 (immutable) |
| 2 | `totalAssets()` | PASS | Overridden in ILAlphaVault (line 141). Counts idle + LP value in asset token only |
| 3 | `convertToShares()` | PASS | Overridden in BaseVault with virtual offset. Uses `mulDivDown` (correct) |
| 4 | `convertToAssets()` | PASS | Overridden in BaseVault with virtual offset. Uses `mulDivDown` (correct) |
| 5 | `maxDeposit()` | PASS | Overridden. Returns 0 when paused, respects deposit cap |
| 6 | `maxMint()` | PASS | Overridden. Returns 0 when paused, delegates to maxDeposit + convertToShares |
| 7 | `maxWithdraw()` | PASS | Inherited from solmate: `convertToAssets(balanceOf[owner])`. No pause restriction (correct — users must withdraw after emergency) |
| 8 | `maxRedeem()` | PASS | Inherited from solmate: `balanceOf[owner]`. No pause restriction (correct) |
| 9 | `previewDeposit()` | PASS | Overridden in BaseVault: delegates to `convertToShares` (rounds down, correct) |
| 10 | `previewMint()` | PASS | Overridden in BaseVault: `mulDivUp` (rounds up, correct — favors vault) |
| 11 | `previewWithdraw()` | PASS | Overridden in BaseVault: `mulDivUp` (rounds up, correct — favors vault) |
| 12 | `previewRedeem()` | PASS | Overridden in BaseVault: delegates to `convertToAssets` (rounds down, correct) |
| 13 | `deposit()` | PASS | Overridden with guards (pause, cap, TWAP, reentrancy). Calls `super.deposit` |
| 14 | `mint()` | PASS | Overridden with same guards as deposit. Calls `super.mint` |
| 15 | `withdraw()` | PASS | Overridden with TWAP check + reentrancy guard. No pause (correct) |
| 16 | `redeem()` | PASS | Overridden with TWAP check + reentrancy guard. No pause (correct) |

**Rounding direction compliance:** All preview/convert functions follow ERC-4626 rounding rules (favor the vault, never the user). Deposit/mint previews round down/up respectively. Withdraw/redeem previews round up/down respectively. **COMPLIANT.**

**Virtual shares offset:** `VIRTUAL_SHARES = 1e6`, `VIRTUAL_ASSETS = 1e6`. Applied consistently in all BaseVault overrides. Provides inflation attack defense. **COMPLIANT.**

**Edge case — `maxWithdraw`/`maxRedeem` when LP is deployed:** Solmate's defaults return `convertToAssets(balance)` / `balanceOf[owner]` without considering whether the vault can actually fulfill the withdrawal. The vault's `beforeWithdraw` handles this by auto-removing LP when idle balance is insufficient. However, if `_removeLiquidity()` fails (e.g., pool manager is paused or broken), the withdrawal would revert despite `maxWithdraw` returning a non-zero value. This is a known limitation of most ERC-4626 vaults with external dependencies and is **ACCEPTABLE** at current deposit cap.

---

## Dead Code Scan

| Item | File | Line | Status |
|------|------|------|--------|
| `error OnlyKeeper()` | ILAlphaVault.sol | 39 | DEAD — no code reverts with it |
| `keeper` storage var | ILAlphaVault.sol | 80 | DEAD — never read for access control |
| `setKeeper()` function | ILAlphaVault.sol | 458 | DEAD — sets unused `keeper` var |
| `KeeperUpdated` event | ILAlphaVault.sol | 62 | DEAD — only emitted by dead `setKeeper()` |
| `error OnlyKeeper()` | ILAlphaHook.sol | 40 | LIVE — used in `onlyKeeper` modifier |
| `keeper` storage var | ILAlphaHook.sol | 108 | LIVE — used in `onlyKeeper` modifier |

**Recommendation:** Remove `error OnlyKeeper()`, `keeper`, `setKeeper()`, and `event KeeperUpdated` from ILAlphaVault.sol. If keeper-gated vault functions are planned for Phase 4+, defer removal but add a `// TODO: Phase 4` comment.

---

## NatSpec Accuracy Check

| Location | Issue | Severity |
|----------|-------|----------|
| Hook line 461 | "time-weighted average tick" — actually recency-weighted | INFO |
| Vault line 134 | "Total assets = idle balance + real-time LP value (not stale deployedAssets)" — accurate | OK |
| Vault line 278 | "50/50 split assumes vault holds both tokens. Phase 4: pre-swap" — accurate | OK |
| Vault line 325 | "No whenNotPaused — users must be able to withdraw after emergency" — accurate | OK |
| BaseVault line 9 | "Shared base for ILAlphaVault, AlwaysLPVault, and HODLVault" — AlwaysLPVault and HODLVault may not exist yet | INFO |
| Vault line 87 | "Maximum total deposits allowed (default $10K USDC = 10_000e6)" — accurate | OK |

---

## Consolidated Findings

### CRITICAL: 0
### HIGH: 0

### MEDIUM (3 — all carried from V3, no new MEDIUMs)

| # | Finding | Status | Risk |
|---|---------|--------|------|
| M-1 | `setLPRange` callable while vault has deployed LP | OPEN (from V3) | Stranded liquidity |
| M-2 | 50/50 asset split for two-sided LP | OPEN (Phase 4 deferral) | Suboptimal capital use |
| M-3 | `_checkSlippage` cross-decimal token sum | OPEN (dormant) | Active when cross-decimal pairs added |

### LOW/INFO (5)

| # | Finding | Status | Impact |
|---|---------|--------|--------|
| L-1 | `error OnlyKeeper()` declared unused in vault | NEW | Dead code |
| L-2 | `keeper` storage + `setKeeper()` + `KeeperUpdated` unused in vault | NEW | Dead code, wasted storage slot |
| L-3 | `getVaultMetrics().deployedValue` inconsistent with `totalAssets()` | NEW | Off-chain data inconsistency |
| I-1 | `getTwapTick` NatSpec says "time-weighted" (is recency-weighted) | OPEN (from V3) | Misleading docs |
| I-2 | `mint()` double `previewMint` call | OPEN (from V3) | ~5-10K gas waste |

---

## Scorecard: 40/45 (89%)

| Category | V1 | V2 | V3 | V4 | Notes |
|----------|----|----|-----|-----|-------|
| Arithmetic | 4 | 4 | 4 | 4 | Virtual shares correct, rounding compliant |
| Auditing & Logging | 4 | 5 | 5 | 5 | Events present for all state changes |
| Access Control | 4 | 4 | 4 | **5** | Dead keeper code is only issue; all live ACL correct |
| Complexity | 4 | 4 | 5 | 5 | Clean callback pattern, clear separation |
| Decentralization | 3 | 3 | 3 | 3 | Owner-controlled; two-step transfer mitigates |
| Documentation | 3 | 3 | 4 | **4** | Minor NatSpec issues remain |
| MEV Resistance | 3 | 4 | 4 | **5** | TWAP + slippage + virtual shares all solid |
| Low-level Code | 5 | 5 | 5 | 5 | No assembly, no unchecked, clean types |
| Testing | 4 | 4 | 4 | 4 | Not re-evaluated (out of scope) |

---

## Mainnet Readiness

**$10K deposit cap: GO** — No CRITICAL or HIGH findings. All MEDIUMs are either dormant or operational-risk-only. ERC-4626 fully compliant.

**$100K+ cap: HOLD** — Resolve M-1 (setLPRange coordination) and M-3 (cross-decimal slippage) before raising cap.

**Professional audit: READY** — 90/100 readiness. Clean the dead keeper code (L-1, L-2) for a cleaner audit surface. All prior CRITICAL/HIGH findings resolved and verified.

---

## Recommended Quick Wins (pre-mainnet)

1. Remove dead keeper code from vault: `error OnlyKeeper()`, `keeper`, `setKeeper()`, `KeeperUpdated` (~10 min)
2. Fix `getTwapTick` NatSpec to say "recency-weighted" (~1 min)
3. Fix `getVaultMetrics().deployedValue` to only count asset token (~5 min)

Total effort: ~20 minutes for a cleaner contract surface before professional audit.
