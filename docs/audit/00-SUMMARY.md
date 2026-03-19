# IL Alpha Vault — Trail of Bits Security Audit Summary

**Date:** 2026-03-20
**Scope:** 6 Solidity files in `contracts/src/` (~1,150 LOC)
**Methodology:** 8-phase Trail of Bits framework (static analysis, sharp edges, property testing, entry points, context building, spec compliance, differential review, secure contracts assessment)

---

## Code Maturity Score: 34/45 (76%)

| Category | Score |
|----------|-------|
| Arithmetic | 4/5 |
| Auditing & Logging | 4/5 |
| Access Control | 4/5 |
| Complexity Management | 4/5 |
| Decentralization | 3/5 |
| Documentation | 3/5 |
| MEV Resistance | 3/5 |
| Low-level Code | 5/5 |
| Testing | 4/5 |

---

## Aggregate Findings

| Severity | Count |
|----------|-------|
| CRITICAL | 4 |
| HIGH | 8 |
| MEDIUM | 10 |
| LOW | 9 |
| INFO | 7 |
| **Total** | **38** |

---

## CRITICAL Findings (Must Fix Before Mainnet)

### C-1: Withdrawal Fee Never Deducted from User Transfer
- **Files:** `ILAlphaVault.sol:299-311`
- **Impact:** `accumulatedFees` grows as phantom balance. `claimFees()` drains other depositors' principal.
- **Found by:** Phases 1, 2, 3, 4, 8 (confirmed independently by 5 analyses)
- **Fix:** Override `withdraw()`/`redeem()` to deduct fee from transfer amount, or restructure fee collection within the ERC-4626 flow.

### C-2: `mint()` Bypasses All Deposit Guards
- **Files:** `ILAlphaVault.sol` (missing override)
- **Impact:** `mint()` is inherited from ERC4626 without override, bypassing `whenNotPaused`, `nonReentrant`, `DepositTooSmall`, `DepositCapExceeded`, and `_checkTWAP()`.
- **Found by:** Phases 1, 4
- **Fix:** Override `mint()` with same guards as `deposit()`.

### C-3: `setPoolKey()` Callable with Active Liquidity
- **Files:** `ILAlphaVault.sol:403-411`
- **Impact:** Changing pool key while `deployedLiquidity > 0` permanently strands LP position in old pool. Unrecoverable fund loss.
- **Found by:** Phases 1, 2
- **Fix:** Add `require(deployedLiquidity == 0, "Active LP")` guard.

### C-4: `setTwapThreshold()` Has No Bounds Validation
- **Files:** `ILAlphaVault.sol:425-427`
- **Impact:** Setting to 0 bricks all deposits/withdrawals. Setting to `type(int24).max` disables manipulation protection.
- **Found by:** Phase 2
- **Fix:** Add min/max bounds (e.g., `10 <= threshold <= 2000`).

---

## HIGH Findings (Fix Before Any Real Funds)

### H-1: TWAP Check Uses Single Stale Tick, Not True TWAP
- `ILAlphaVault.sol:337-355` — `lastTick` from hook is just the most recent swap tick, trivially manipulable.

### H-2: No Slippage Protection on LP Add/Remove
- `ILAlphaVault.sol:224-265, 275-295` — `rebalance()` is public and sandwichable via MEV.

### H-3: 50/50 Asset Split Assumes Vault Holds Both Tokens
- `ILAlphaVault.sol:233-235` — Vault only holds one asset token but tries to provide two-sided LP.

### H-4: Keeper `pushVolEstimate` Rate Limit is 4x, Not 2x as Documented
- `ILAlphaHook.sol:366` — Comment says "2x" but code uses `currentVar * 4`. When `ewmaVar == 0`, limit is `uint128.max`.

### H-5: `withdraw()`/`redeem()` Missing Reentrancy Guard
- `ILAlphaVault.sol` — Only `deposit()` has `nonReentrant`. Withdrawal path makes external calls without guard.

### H-6: AlwaysLPVault Double-Counts Assets
- `AlwaysLPVault.sol:33-39` — `rebalance()` adds to `deployedAssets` but tokens stay in vault, causing `totalAssets()` double-count.

### H-7: `totalAssets()` Sums Two Token Amounts Without Price Conversion
- `ILAlphaVault.sol:149` — `idle + lpValue0 + lpValue1` treats different tokens as fungible.

### H-8: Admin Parameter Changes Emit No Events
- Multiple admin setters (`setKeeper`, `setLambda`, `setPoolKey`, etc.) are silent — unmonitorable.

---

## MEDIUM Findings

1. **M-1:** Pool key change orphans existing LP position tracking
2. **M-2:** Remove liquidity uses current tick range, not deployment range
3. **M-3:** `_computeFeeAndIL` fee/IL units may not be comparable (different scaling)
4. **M-4:** No zero-address checks on `setKeeper()`, `transferOwnership()`
5. **M-5:** `SwapHelper` uses raw `transferFrom` instead of `safeTransferFrom`
6. **M-6:** Volume spike detection bypass allows forced LP deactivation
7. **M-7:** EWMA oracle can be slowly gamed by attacker controlling swap flow
8. **M-8:** No timelock on critical parameter changes (withdrawal fee, TWAP threshold)
9. **M-9:** `LiquidityAmounts` imported from test utils (`v4-core/test/utils/`)
10. **M-10:** `emergencyWithdraw` does not handle negative deltas (owes tokens case)

---

## Test Coverage Gaps (13 identified)

1. No test for `mint()` bypass of deposit guards
2. No test for `_checkTWAP` revert path
3. No test for `beforeWithdraw` triggering LP removal
4. No invariant/stateful testing
5. No cross-contract reentrancy tests
6. No test for `setPoolKey` with active liquidity
7. No test for extreme EWMA values
8. No multi-block sandwich attack simulation
9. No test for `claimFees()` exceeding available balance
10. No test for `redeem()` path
11. No test for `setTwapThreshold(0)` bricking
12. No fuzz test for `_computeFeeAndIL` precision
13. No test for keeper vol push when `ewmaVar == 0`

---

## Remediation Priority

| Priority | Finding | Effort |
|----------|---------|--------|
| 1 (immediate) | C-1: Fix withdrawal fee accounting | ~30 min |
| 2 (immediate) | C-2: Override `mint()` with guards | ~10 min |
| 3 (immediate) | C-3: Guard `setPoolKey` against active LP | ~5 min |
| 4 (immediate) | C-4: Bound `setTwapThreshold` | ~5 min |
| 5 (before testnet) | H-1: Implement real TWAP or accumulator | ~2 hours |
| 6 (before testnet) | H-2: Add slippage protection to rebalance | ~1 hour |
| 7 (before testnet) | H-3: Fix single-token LP provision | ~2 hours |
| 8 (before testnet) | H-5: Add nonReentrant to withdraw/redeem | ~15 min |
| 9 (before audit) | H-4: Fix rate limit (4x → 2x) | ~5 min |
| 10 (before audit) | H-8: Add events to admin setters | ~30 min |

---

## Reports Index

| # | Phase | File | Lines | Findings |
|---|-------|------|-------|----------|
| 1 | Static Analysis | [01-static-analysis.md](01-static-analysis.md) | 455 | 22 |
| 2 | Sharp Edges | [02-sharp-edges.md](02-sharp-edges.md) | 250 | 23 |
| 3 | Property-Based Testing | [03-property-based-testing.md](03-property-based-testing.md) | 628 | 27 invariants, 3 bugs |
| 4 | Entry Points | [04-entry-points.md](04-entry-points.md) | 195 | 46 entry points |
| 5 | Audit Context | [05-audit-context.md](05-audit-context.md) | 428 | Architecture + threat model |
| 6 | Spec Compliance | [06-spec-compliance.md](06-spec-compliance.md) | 447 | Spec vs code gaps |
| 7 | Differential Review | [07-differential-review.md](07-differential-review.md) | 262 | Recent change analysis |
| 8 | Secure Contracts | [08-building-secure-contracts.md](08-building-secure-contracts.md) | 213 | Maturity 76%, vuln scan |

---

**Overall Assessment:** The codebase shows strong security awareness (virtual shares, two-step ownership, emergency pause, keeper rate limiting, EWMA oracle). However, **4 critical bugs** must be fixed before any real funds are deployed. The withdrawal fee accounting bug (C-1) is the most dangerous — independently confirmed by 5 of 8 analysis phases. After fixing criticals and highs, the protocol would be a strong candidate for professional audit.

**Estimated Audit Readiness: 55/100** (currently) → **85/100** (after fixing C-1 through C-4 and H-1 through H-8)
