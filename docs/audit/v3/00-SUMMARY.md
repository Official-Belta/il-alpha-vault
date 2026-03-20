# IL Alpha Vault — V3 Final Audit Summary

**Date:** 2026-03-20
**Scope:** ILAlphaHook.sol, ILAlphaVault.sol, BaseVault.sol (post-V2 fixes)
**Key change:** Withdrawal fee mechanism completely removed (root cause elimination)

---

## V1 → V2 → V3 Journey

| Metric | V1 | V2 | V3 |
|--------|----|----|-----|
| CRITICAL | 4 | 0 | **0** |
| HIGH | 8 | 2 (regression) | **0** |
| MEDIUM | 10 | 6 | **4** |
| LOW/INFO | 16 | 3 | **6** |
| Risk Rating | MEDIUM-HIGH | MEDIUM | **LOW-MEDIUM** |
| Maturity | 34/45 (76%) | 36/45 (80%) | **38/45 (84%)** |
| Audit Readiness | 55/100 | 75/100 | **85/100** |

---

## V2 Finding Resolution

| V2 Finding | Status |
|------------|--------|
| R-1 HIGH: ERC-4626 non-conformance (fee) | **FIXED** — fee removed entirely |
| R-2 HIGH: accumulatedFees phantom balance | **FIXED** — fee removed entirely |
| R-3 MEDIUM-HIGH: TWAP same-block flooding | **FIXED** — per-block dedup added |
| R-4 MEDIUM: LP remove slippage | **ACCEPTED** — TWAP protects; documented |
| R-5 MEDIUM: cross-decimal slippage check | **OPEN** — dormant (same-decimal pairs only for now) |
| R-6 MEDIUM: setMaxSlippageBps(0) brick | **FIXED** — min 10 bps |
| R-7 MEDIUM: TWAP fallback to lastTick | **ACCEPTED** — documented safe default |
| R-8 LOW: missing SlippageUpdated event | **FIXED** |
| R-9 LOW: mint() double previewMint | **OPEN** — gas only |
| R-10 LOW: PoolKeyUpdated no params | **OPEN** |
| R-11 LOW: _ensureIdle removes all LP | **ACCEPTED** — simplicity tradeoff |

---

## Remaining Findings (V3)

### CRITICAL: 0
### HIGH: 0

### MEDIUM (4)

1. **`maxDeposit` doesn't reflect paused state + `maxMint` not overridden** — ERC-4626 violation. When paused, maxDeposit doesn't return 0, maxMint ignores deposit cap/paused. Integrating protocols receive incorrect limits.

2. **`setLPRange` callable while vault has deployed LP** — Hook can change tick range, causing vault to remove liquidity at wrong ticks. Fix: coordinate with vault's deployedLiquidity state.

3. **H-3: 50/50 asset split for LP** — Vault holds one token but splits for two-sided LP. Documented deferral to Phase 4 (pre-swap implementation).

4. **`_checkSlippage` sums different-decimal tokens** — Currently dormant (USDC/USDC pairs), becomes active risk with mixed-decimal pairs (e.g., USDC/WETH).

### LOW/INFO (6)

5. `PoolKeyUpdated` event declared but never emitted in `setPoolKey()`
6. Dead `_getDeployedLPValue()` call in `_executeRemoveLiquidity` (~5K gas waste)
7. `mint()` calls `previewMint` twice (gas inefficiency)
8. Stale comment "fee deferred post-audit" (fee was intentionally removed)
9. `getTwapTick` NatSpec says "time-weighted" but implementation is recency-weighted
10. Vault `onlyKeeper` modifier not applied to any function (effectively dead code)

---

## Scorecard: 38/45 (84%)

| Category | V1 | V2 | V3 |
|----------|----|----|-----|
| Arithmetic | 4 | 4 | 4 |
| Auditing & Logging | 4 | 5 | 5 |
| Access Control | 4 | 4 | 4 |
| Complexity | 4 | 4 | **5** ↑ |
| Decentralization | 3 | 3 | 3 |
| Documentation | 3 | 3 | **4** ↑ |
| MEV Resistance | 3 | 4 | 4 |
| Low-level Code | 5 | 5 | 5 |
| Testing | 4 | 4 | 4 |

---

## Mainnet Readiness

**$10K deposit cap: GO** — MEDIUM risk acceptable. Max extractable value per attack ~$200-500.

**$100K+ cap: HOLD** — Fix LP remove slippage and cross-decimal check first.

**Professional audit: READY** — All critical/high resolved. 85/100 readiness score. Remaining items are medium/low severity with clear fixes.

---

## Reports

| # | File | Lines |
|---|------|-------|
| 1 | [01-static-sharp-edges.md](01-static-sharp-edges.md) | 197 |
| 2 | [02-spec-compliance.md](02-spec-compliance.md) | complete |
| 3 | [03-entry-threat-model.md](03-entry-threat-model.md) | 335 |
| 4 | [04-final-assessment.md](04-final-assessment.md) | 264 |
