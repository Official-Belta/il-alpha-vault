# IL Alpha Vault — V2 Re-Audit Summary

**Date:** 2026-03-20
**Scope:** 6 Solidity files, post-fix re-audit
**Methodology:** 8-phase Trail of Bits framework (same as v1)
**Previous audit:** docs/audit/00-SUMMARY.md (38 findings)

---

## V1 → V2 Fix Verification

| Severity | V1 Found | Fixed | Partially Fixed | Not Fixed | Accepted |
|----------|----------|-------|-----------------|-----------|----------|
| CRITICAL | 4 | **4 ✅** | 0 | 0 | 0 |
| HIGH | 8 | **6 ✅** | 1 (H-2) | 0 | 1 (H-3→Phase 4) |
| MEDIUM | 10 | **6 ✅** | 0 | 2 | 2 |
| LOW | 9 | **5 ✅** | 0 | 1 | 3 |
| INFO | 7 | 3 | 0 | 0 | 4 |
| **Total** | **38** | **24** | **1** | **3** | **10** |

**All 4 CRITICALs resolved. No CRITICAL findings remain.**

---

## Code Maturity Score: 36/45 (80%) ↑ from 34/45 (76%)

| Category | V1 | V2 | Change |
|----------|----|----|--------|
| Arithmetic | 4/5 | 4/5 | — |
| Auditing & Logging | 4/5 | 5/5 | ↑ events added |
| Access Control | 4/5 | 4/5 | — |
| Complexity Management | 4/5 | 4/5 | — |
| Decentralization | 3/5 | 3/5 | — |
| Documentation | 3/5 | 3/5 | — |
| MEV Resistance | 3/5 | 4/5 | ↑ TWAP + slippage |
| Low-level Code | 5/5 | 5/5 | — |
| Testing | 4/5 | 4/5 | — |

---

## Risk Rating: MEDIUM ↓ from MEDIUM-HIGH

## Audit Readiness: 75/100 ↑ from 55/100

---

## NEW Findings From V2 Fixes

8개 에이전트에서 독립 분석 후 크로스-밸리데이션된 신규 이슈:

### HIGH (2건 — 동일 근본 원인)

#### R-1: ERC-4626 Non-Conformance in withdraw/redeem
- **Confirmed by:** Static Analysis, Entry Points, Sharp Edges, Spec Compliance (4/8 에이전트)
- **File:** `ILAlphaVault.sol:329-370`
- **Problem:** `withdraw(assets)` burns shares computed from full `assets` but transfers `assets - fee`. ERC-4626 spec requires `withdraw(X)` to deliver exactly X assets. `previewWithdraw`/`previewRedeem`/`maxWithdraw` don't account for fees.
- **Impact:** Integrating protocols (routers, aggregators, yield optimizers) will misaccount user balances. Late depositors receive inflated share price.
- **Fix:** Override `previewWithdraw`/`previewRedeem` to include fee. Or restructure: burn fewer shares so user receives exactly `assets`.

#### R-2: `accumulatedFees` Not Subtracted from `totalAssets()`
- **Confirmed by:** Static Analysis, Entry Points, Sharp Edges, Secure Contracts (4/8 에이전트)
- **File:** `ILAlphaVault.sol:152-168`
- **Problem:** Fees stay in `asset.balanceOf(address(this))` and are counted as vault assets. Share price is inflated by unclaimed fees. When `claimFees()` runs, share price drops — punishing remaining depositors.
- **Fix:** `return idle - accumulatedFees + lpValue` in `totalAssets()`.

### MEDIUM-HIGH (1건)

#### R-3: TWAP Buffer Defeatable via Same-Block Multi-Swap
- **Confirmed by:** Static Analysis, Audit Context, Sharp Edges, Differential Review (4/8 에이전트)
- **File:** `ILAlphaHook.sol:448-455`
- **Problem:** `_recordTickObservation` records every swap with no per-block deduplication. 10 swaps in one block fills the entire circular buffer with attacker-controlled tick values.
- **Impact:** Attacker bypasses TWAP manipulation protection, enables sandwich attacks on deposit/withdraw.
- **Fix:** Add `if (obs.timestamp == uint40(block.timestamp)) return;` check, or track `lastRecordedBlock`.

### MEDIUM (5건)

#### R-4: No Slippage Protection on LP Removal
- **Confirmed by:** Static Analysis, Entry Points, Audit Context, Sharp Edges, Differential Review (5/8 에이전트)
- **File:** `ILAlphaVault.sol:312-323`
- **Fix:** Add `_checkSlippage` to `_executeRemoveLiquidity`.

#### R-5: `_checkSlippage` Sums Different-Decimal Tokens
- **Confirmed by:** Sharp Edges
- **File:** `ILAlphaVault.sol:373-377`
- **Fix:** Compare each token delta independently, or normalize to same decimals.

#### R-6: `setMaxSlippageBps(0)` Bricks LP Rebalancing
- **Confirmed by:** Sharp Edges
- **File:** `ILAlphaVault.sol:513-516`
- **Fix:** Add `require(_bps >= 10, "Min 0.1%")`.

#### R-7: TWAP Fallback Degrades to V1 Behavior
- **Confirmed by:** Differential Review
- **Problem:** When all observations are >1hr old or uninitialized, `getTwapTick` falls back to `lastTick` — the exact weakness v1 had.
- **Fix:** Revert instead of falling back, or require minimum observation count.

#### R-8: `setMaxSlippageBps` Missing Event
- **Confirmed by:** Entry Points, Sharp Edges
- **Fix:** Add `emit SlippageUpdated(oldBps, newBps)`.

### LOW (3건)

- **R-9:** `mint()` calls `previewMint` twice (gas inefficiency)
- **R-10:** `PoolKeyUpdated` event has no parameters (un-indexable)
- **R-11:** `_ensureIdle` removes ALL LP even for small shortfalls (unnecessary churn)

---

## Cross-Validation Matrix

How many of the 8 independent agents found each issue:

| Finding | Static | Sharp | Property | Entry | Context | Spec | Diff | Secure | Count |
|---------|--------|-------|----------|-------|---------|------|------|--------|-------|
| R-1 ERC-4626 fee | ✅ | ✅ | | ✅ | | ✅ | | ✅ | **5/8** |
| R-2 accumulatedFees | ✅ | ✅ | | ✅ | | | | ✅ | **4/8** |
| R-3 TWAP same-block | ✅ | ✅ | | | ✅ | | ✅ | | **4/8** |
| R-4 Remove slippage | ✅ | ✅ | | ✅ | ✅ | | ✅ | ✅ | **6/8** |
| R-5 Decimal mismatch | | ✅ | | | | | | | **1/8** |
| R-6 Slippage 0 brick | | ✅ | | | | | | | **1/8** |

---

## Remediation Priority

| Priority | Finding | Effort | Impact |
|----------|---------|--------|--------|
| 1 | R-2: Subtract accumulatedFees from totalAssets | ~5 min | Share price accuracy |
| 2 | R-1: Fix preview functions to include fee | ~30 min | ERC-4626 compliance |
| 3 | R-3: TWAP same-block deduplication | ~10 min | Oracle manipulation |
| 4 | R-4: Add slippage check to removeLiquidity | ~15 min | Sandwich protection |
| 5 | R-6: Min bound for maxSlippageBps | ~5 min | Operational safety |
| 6 | R-5: Fix cross-decimal slippage check | ~20 min | Correct validation |
| 7 | R-7: TWAP fallback behavior | ~10 min | Oracle integrity |
| 8 | R-8: Missing event | ~5 min | Monitoring |

**Total estimated fix time: ~1.5 hours**

---

## Reports Index

| # | Phase | File | Status |
|---|-------|------|--------|
| 1 | Static Analysis v2 | [01-static-analysis.md](01-static-analysis.md) | ✅ Complete |
| 2 | Sharp Edges v2 | [02-sharp-edges.md](02-sharp-edges.md) | ✅ Complete |
| 3 | Property Testing v2 | [03-property-based-testing.md](03-property-based-testing.md) | ✅ Complete |
| 4 | Entry Points v2 | [04-entry-points.md](04-entry-points.md) | ✅ Complete |
| 5 | Audit Context v2 | [05-audit-context.md](05-audit-context.md) | ✅ Complete |
| 6 | Spec Compliance v2 | [06-spec-compliance.md](06-spec-compliance.md) | ✅ Complete |
| 7 | Differential Review v2 | [07-differential-review.md](07-differential-review.md) | ✅ Complete |
| 8 | Secure Contracts v2 | [08-building-secure-contracts.md](08-building-secure-contracts.md) | ✅ Complete |

---

## Overall Assessment

**V1 → V2 개선 요약:**
- CRITICAL: 4 → 0 (전체 해결)
- Risk: MEDIUM-HIGH → MEDIUM
- Maturity: 76% → 80%
- Audit Readiness: 55 → 75 → (R-1~R-8 수정 후) **~90**

**남은 작업:** R-1~R-8 수정 (~1.5시간) → 프로페셔널 감사 의뢰 준비 완료. 현재 코드에 자금 탈취 가능한 CRITICAL은 없으나, ERC-4626 비준수(R-1)와 share price 왜곡(R-2)은 통합 프로토콜과의 호환성 문제를 유발하므로 메인넷 전 반드시 수정 필요.
