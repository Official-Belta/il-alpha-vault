# 03 - Entry Point Analysis & Threat Model (v3)

Date: 2026-03-20
Previous version: `docs/audit/v2/04-entry-points.md`, `docs/audit/v2/05-audit-context.md`

---

## V3 Key Changes from V2

1. **Fee functions removed:** `claimFees()`, `setWithdrawalFeeBps()`, `withdrawalFeeBps`, `accumulatedFees` all deleted
2. **withdraw/redeem simplified:** Standard ERC-4626 flow + `nonReentrant` + `_checkTWAP()`, no fee deduction
3. **TWAP per-block dedup (R-3):** `_recordTickObservation()` now skips if previous observation has same `block.timestamp`
4. **`setMaxSlippageBps()` bounded:** Range enforced to 10-500 bps with event emission

---

## 1. Entry Point Inventory (V3)

**Access Level Key:**
- **PUBLIC** -- callable by anyone
- **KEEPER** -- restricted to `keeper` or `owner`
- **OWNER** -- restricted to `owner` only
- **POOL_MANAGER** -- restricted to Uniswap V4 PoolManager
- **PENDING_OWNER** -- restricted to `pendingOwner`

### 1.1 ILAlphaHook.sol (9 entry points -- unchanged from V2)

| # | Function | Access | State Changes | Risk |
|---|----------|--------|---------------|------|
| 1 | `afterInitialize()` | POOL_MANAGER | `poolStates`, `volOracles` | LOW |
| 2 | `afterSwap()` | POOL_MANAGER | `volOracles`, `poolStates`, `tickObservations`, `observationIndex` | MEDIUM |
| 3 | `pushVolEstimate()` | KEEPER | `volOracles.ewmaVar`, `.lastTimestamp` | MEDIUM |
| 4 | `triggerEvaluation()` | KEEPER | `poolStates.isLPActive`, `.lastToggleTime` | MEDIUM |
| 5 | `setLPRange()` | OWNER | `poolStates.tickLower`, `.tickUpper` | MEDIUM |
| 6 | `transferOwnership()` | OWNER | `pendingOwner` | LOW |
| 7 | `acceptOwnership()` | PENDING_OWNER | `owner`, `pendingOwner` | LOW |
| 8 | `setKeeper()` | OWNER | `keeper` | LOW |
| 9 | `setLambda()` | OWNER | `volOracles.lambda` | MEDIUM |

### 1.2 ILAlphaVault.sol (15 entry points -- was 17 in V2)

| # | Function | Access | Modifiers | Value Flow | Risk |
|---|----------|--------|-----------|------------|------|
| 1 | `deposit()` | PUBLIC | `whenNotPaused`, `nonReentrant` | Tokens IN | MEDIUM |
| 2 | `mint()` | PUBLIC | `whenNotPaused`, `nonReentrant` | Tokens IN | MEDIUM |
| 3 | `withdraw()` | PUBLIC | `nonReentrant` | Tokens OUT | MEDIUM |
| 4 | `redeem()` | PUBLIC | `nonReentrant` | Tokens OUT | MEDIUM |
| 5 | `rebalance()` | PUBLIC | `whenNotPaused`, `nonReentrant` | Tokens <-> PoolManager | MEDIUM-HIGH |
| 6 | `unlockCallback()` | POOL_MANAGER | -- | Tokens <-> PoolManager | MEDIUM |
| 7 | `transferOwnership()` | OWNER | -- | None | LOW |
| 8 | `acceptOwnership()` | PENDING_OWNER | -- | None | LOW |
| 9 | `setPoolKey()` | OWNER | -- | None | MEDIUM |
| 10 | `setPaused()` | OWNER | -- | None | LOW |
| 11 | `setKeeper()` | OWNER | -- | None | LOW |
| 12 | `setDepositCap()` | OWNER | -- | None | LOW |
| 13 | `setTwapThreshold()` | OWNER | -- | None | LOW |
| 14 | `setMaxSlippageBps()` | OWNER | -- | None | LOW |
| 15 | `emergencyWithdraw()` | OWNER | `nonReentrant` | Tokens IN (LP removed) | MEDIUM |

#### Inherited ERC20 (from solmate): `transfer`, `transferFrom`, `approve`, `permit` -- 4 entry points, all PUBLIC, LOW risk.

### 1.3 Removed Entry Points in V3 (vs V2)

| Function | Reason | Impact |
|----------|--------|--------|
| `setWithdrawalFeeBps()` | Fee system removed | Eliminates fee misconfiguration risk |
| `claimFees()` | Fee system removed | Eliminates accumulatedFees phantom balance issue |

### 1.4 Summary Statistics

| Contract | Total State-Changing | PUBLIC | KEEPER | OWNER | POOL_MANAGER | PENDING_OWNER |
|----------|---------------------|--------|--------|-------|--------------|---------------|
| ILAlphaHook | 9 | 0 | 2 | 4 | 2 | 1 |
| ILAlphaVault | 19 (incl. ERC20) | 8 | 0 | 7 | 1 | 1 |
| **Total** | **28** | **8** | **2** | **11** | **3** | **2** |

**V3 total: 28 entry points** (was 30 in V2 for these two contracts; -2 from fee removal).

---

## 2. Top 5 Risk Entry Points (V3 Re-Ranking)

### Rank 1: `ILAlphaVault.rebalance()` -- MEDIUM-HIGH

**File:** `contracts/src/ILAlphaVault.sol`, line 203

**Why highest risk in V3:** With fee-related vectors removed, rebalance is now the primary value extraction surface.

**Attack surface:**
- Publicly callable -- anyone can trigger, attacker controls timing
- Slippage check on `addLiquidity` (bounded by `maxSlippageBps`, default 1%)
- **No slippage check on `removeLiquidity`** -- vault accepts whatever the pool returns
- 50/50 split assumption in `_computeLiquidity()` leaks value when price is off-center
- Sandwich: attacker manipulates price, calls `rebalance()`, profits from slippage

**Mitigations present:** Slippage check on add (H-2), TWAP check on deposit/withdraw, `nonReentrant`, `whenNotPaused`.

**Residual gap:** `_executeRemoveLiquidity()` (line 306-322) has no minimum output check. Comment on line 319-320 explicitly acknowledges this: "Not checking slippage on removal to avoid bricking emergency withdraw."

### Rank 2: `ILAlphaVault.withdraw()` / `redeem()` -- MEDIUM

**File:** `contracts/src/ILAlphaVault.sol`, lines 327-338

**V3 improvement:** With fees removed, the ERC-4626 non-conformance (V2 finding V2-3) is resolved. `withdraw(assets)` now delivers exactly `assets` to the receiver. The `accumulatedFees` phantom balance issue (V2 finding V2-B) is also eliminated.

**Remaining attack surface:**
- `beforeWithdraw()` may trigger `_removeLiquidity()` if idle < requested -- same no-slippage-on-removal gap
- TWAP check via `_checkTWAP()` protects against spot price manipulation
- No `whenNotPaused` (by design -- users must always be able to exit)

**Residual risk:** If an attacker can manipulate the TWAP (see Rank 4), they can deposit/withdraw at favorable share prices.

### Rank 3: `ILAlphaHook.pushVolEstimate()` -- MEDIUM

**File:** `contracts/src/ILAlphaHook.sol`, line 377

**V3 status:** Unchanged from V2. 2x rate limit, 1e18 zero baseline cap.

**Residual risk:**
- Exponential ratcheting: 1.5x per call, ~11 calls to reach 100x
- Downward suppression: pushing 0 repeatedly halves variance each call (5 calls = 1/32 of original)
- No per-block or per-hour rate limiting on calls
- Keeper key is single point of trust (shares `onlyKeeper` with owner)

### Rank 4: `ILAlphaHook.afterSwap()` / TWAP Oracle -- MEDIUM

**File:** `contracts/src/ILAlphaHook.sol`, line 235

**V3 improvement:** R-3 fix adds per-block deduplication. `_recordTickObservation()` (line 449-452) checks if the previous observation's timestamp matches `block.timestamp` and skips if so. This prevents single-block buffer flooding (V2-1 resolved).

**Remaining attack surface:**
- **Cross-block manipulation:** An attacker can fill all 10 TWAP slots across 10 consecutive blocks (~2 minutes on L1, faster on L2). Cost: gas + swap fees for 10 swaps.
- Recency weighting still heavily favors fresh observations (3600:1 ratio newest:oldest)
- Low-activity pools remain vulnerable: fewer valid observations means easier to dominate the buffer
- Same-block swaps skip vol oracle update (`elapsed == 0` check), so MEV bots can swap without affecting EWMA variance

**Key improvement over V2:** Single-transaction TWAP flooding is no longer possible. Attacker must sustain manipulation across multiple blocks, significantly increasing cost.

### Rank 5: `ILAlphaVault.emergencyWithdraw()` -- MEDIUM

**File:** `contracts/src/ILAlphaVault.sol`, line 484

**Attack surface:**
- Uses `_removeLiquidity()` with no slippage check
- Owner-only, but compromised owner key can force LP removal at manipulated price
- Pauses vault after removal (correct behavior)
- Sandwich attack if owner tx is visible in mempool

---

## 3. Threat Model: V3 Attack Vectors

With fee functions removed, the attack surface is narrower. The remaining vectors center on four themes: (A) sandwich attacks on LP operations, (B) oracle manipulation, (C) keeper compromise, and (D) deposit/withdraw front-running.

### 3.1 Vector A: Sandwich `rebalance()` (LP Add/Remove)

**Mechanism:**
1. Attacker monitors mempool for `rebalance()` calls
2. Front-runs with a large swap to move pool price
3. `rebalance()` executes at manipulated price
4. Attacker back-runs to reverse the swap, capturing profit

**Add liquidity path (slippage protected):**
- `_checkSlippage()` bounds the cost to `expected + expected * maxSlippageBps / 10_000`
- Default `maxSlippageBps = 100` (1%), max configurable 500 (5%)
- **Maximum extractable value per rebalance (add):** `depositCap * maxSlippageBps / 10_000` = `10,000 USDC * 1% = 100 USDC` at default settings. Worst case (500 bps): 500 USDC.

**Remove liquidity path (NO slippage protection):**
- No minimum output check. Vault accepts whatever the pool returns.
- The vault only counts the asset token in `totalAssets()` (H-7 fix), so manipulation that shifts value into the non-asset token causes a real loss.
- **Maximum extractable value per rebalance (remove):** Theoretically up to the full value of deployed LP. Practically bounded by:
  - Pool liquidity depth (attacker needs enough capital to move the price)
  - Gas costs of sandwich
  - Concentrated liquidity range width (1000 ticks = ~10% range)
  - **Realistic estimate for $10K vault:** 2-5% of deployed value = $200-500 per sandwich event. In a thin pool, could be higher.

**Mitigation gap:** The comment at line 319-320 explicitly defers removal slippage to avoid bricking emergency withdraw. This is a conscious tradeoff.

### 3.2 Vector B: TWAP Manipulation (Cross-Block)

**Mechanism (post R-3 dedup fix):**
1. Attacker executes 1 swap per block across 10 blocks to fill the TWAP circular buffer
2. Each swap moves the tick to a manipulated value
3. After 10 blocks, the TWAP reflects the attacker's desired tick
4. Attacker deposits at inflated share price or withdraws at deflated price
5. `_checkTWAP()` passes because the TWAP itself is corrupted

**Cost analysis:**
- 10 swaps across 10 blocks: ~10 * (swap_fee + gas + slippage_on_manipulation_swap)
- For a 0.3% fee pool with $10K liquidity: ~10 * $30 fee + slippage = ~$500-1000 in costs
- Must sustain manipulation for ~2 minutes (10 blocks on L1)
- On L2 (2s blocks): only ~20 seconds, significantly cheaper

**Maximum extractable value:**
- Depends on how far the TWAP can be moved vs `twapThreshold` (default 500 ticks = ~5%)
- If attacker moves price by 5% AND fills TWAP buffer: deposit at 5% discount on share price
- For $10K vault: ~$500 potential profit, but costs ~$500-1000 to execute
- **Net profit on L1: Likely unprofitable** for a $10K vault
- **Net profit on L2: Marginal** -- faster blocks reduce holding cost, may be profitable in thin pools

**Key improvement in V3:** R-3 dedup means this requires 10 separate blocks, not 10 swaps in one transaction. This is dramatically more expensive than V2's single-block attack.

### 3.3 Vector C: Keeper Compromise

**Mechanism:**
1. Attacker obtains keeper key
2. Uses `pushVolEstimate()` to inflate/deflate vol oracle
3. Manipulated vol changes the hook's LP decision (fee yield vs IL cost comparison)
4. Can force LP activation during high-vol periods (pushing vol down) or deactivation during profitable periods (pushing vol up)

**Damage ceiling (2x rate limit):**
- Per call: vol moves by at most 1.5x (blend of current + 2x current)
- To 100x vol: need ~11 calls with no intervening swaps
- Each swap updates EWMA toward true vol (lambda=0.94 decay), partially countering manipulation
- 24-hour cooldown on LP toggle limits how often wrong decisions are forced

**Maximum extractable value:**
- Indirect: keeper cannot directly extract funds, only influence LP toggle decisions
- If keeper forces LP-on during high vol: vault suffers IL. For $10K vault in a 50% vol event: IL ~ 0.5 * 0.5^2 * concentration = ~12.5% * concentration_factor. Realistic: $200-1000 depending on tick range.
- If keeper forces LP-off during calm markets: vault misses fee income. For $10K vault at 0.3% pool fee with $100K daily volume: ~$300/day missed income.
- **Realistic max damage per keeper compromise event:** $500-1000 before detection and key rotation

**Mitigations present:**
- 2x rate limit (H-4)
- 50/50 blend (not raw override)
- Two-step ownership (owner can rotate keeper)
- On-chain events (`KeeperVolPushed`) enable monitoring

### 3.4 Vector D: Front-Run Deposit/Withdraw

**Mechanism:**
1. Attacker monitors mempool for large deposit/withdraw
2. Manipulates pool price before the tx
3. Victim's deposit mints fewer shares (inflated `totalAssets`) or withdraw gets more (deflated `totalAssets`)
4. Attacker reverses manipulation after victim's tx

**Defenses in V3:**
- `_checkTWAP()`: spot tick vs TWAP tick must be within `twapThreshold` (default 500 ticks)
- `nonReentrant` on all user-facing functions
- Deposit cap ($10K default) limits maximum extractable per event
- Virtual shares offset (1e6) prevents first-depositor inflation attack
- R-3 TWAP dedup: attacker can't flood TWAP in single block

**Maximum extractable value:**
- Limited by `twapThreshold`: attacker can only manipulate price by up to ~5% before TWAP check triggers
- For a $10K deposit at 5% manipulation: ~$500 theoretical, minus attack costs
- **Practical estimate:** $50-200 per event after costs, only viable for large deposits approaching the $10K cap

---

## 4. Extractable Value Summary

| Vector | Max Theoretical | Realistic Estimate | Frequency | Annual Risk |
|--------|----------------|--------------------|-----------|-------------|
| Sandwich rebalance (add) | $500 (5% of $10K cap) | $50-100 | Per rebalance (~daily) | $18K-36K |
| Sandwich rebalance (remove) | $500-2000 | $200-500 | Per LP-off event (~weekly) | $10K-26K |
| TWAP manipulation (L1) | $500 | Unprofitable | Rare | ~$0 |
| TWAP manipulation (L2) | $500 | $0-200 | Occasional | $0-5K |
| Keeper compromise | $500-1000 | $500 (one-time) | Rare | $500 |
| Front-run deposit/withdraw | $200-500 | $50-200 | Per large tx | $2K-10K |

**Total estimated annual risk exposure (worst case): ~$30K-77K**

This risk is proportional to `depositCap`. At $10K cap, the risk is bounded. If cap increases to $100K, multiply all estimates by ~10x.

---

## 5. Resolved V2 Findings in V3

| V2 Finding | V2 Severity | V3 Status | Notes |
|------------|-------------|-----------|-------|
| V2-1: TWAP buffer single-block flooding | MEDIUM-HIGH | **RESOLVED** (R-3 fix) | Per-block dedup via timestamp check |
| V2-3: withdraw() transfers less than `assets` | LOW | **RESOLVED** (fee removal) | No fee deduction, standard ERC-4626 now |
| V2-B: accumulatedFees phantom balance | MEDIUM | **RESOLVED** (fee removal) | No fee accumulation |
| V2-A: ERC-4626 non-conformance in withdraw() | LOW | **RESOLVED** (fee removal) | withdraw() now delivers exactly `assets` |
| V2-E: setMaxSlippageBps missing event | LOW | **RESOLVED** | Event `SlippageUpdated` now emitted (line 479) |

---

## 6. Remaining Findings in V3

| # | Finding | Severity | Location | Description |
|---|---------|----------|----------|-------------|
| V3-1 | No slippage check on removeLiquidity | MEDIUM | ILAlphaVault._executeRemoveLiquidity() L306 | Vault accepts any token split on LP removal. Sandwichable. Intentional tradeoff to avoid bricking emergency withdraw. |
| V3-2 | Cross-block TWAP manipulation | LOW-MEDIUM | ILAlphaHook.afterSwap() / getTwapTick() | 10 swaps across 10 blocks fills the buffer. Costly on L1, cheaper on L2. |
| V3-3 | Keeper vol ratcheting (no time rate limit) | LOW-MEDIUM | ILAlphaHook.pushVolEstimate() L377 | 1.5x per call, ~11 calls to 100x. No per-hour limit. |
| V3-4 | TWAP recency weight skew | LOW | ILAlphaHook.getTwapTick() L463 | 3600:1 weight ratio newest:oldest. Single fresh manipulated observation can dominate. |
| V3-5 | setLPRange not gated by vault LP status | LOW | ILAlphaHook.setLPRange() L409 | Owner can change tick range while vault has deployed liquidity at old range. |
| V3-6 | EWMA gameable over ~11 blocks | MEDIUM | ILAlphaHook._updateVolOracle() L299 | Inherent EWMA property. Attacker cost = swap fees + slippage per manipulation swap. |
| V3-7 | TWAP dedup uses timestamp not block.number | INFO | ILAlphaHook._recordTickObservation() L452 | On some L2s, consecutive blocks may share a timestamp. Using `block.number` would be more robust. |
| V3-8 | 50/50 split in _computeLiquidity | LOW | ILAlphaVault._computeLiquidity() L275 | `assets/2, assets/2` assumption leaks value when pool price is off-center vs tick range. |

---

## 7. Overall Risk Assessment for Mainnet Deployment

### 7.1 What Improved in V3

1. **Attack surface reduced:** 2 fewer entry points (fee functions removed). This eliminates an entire class of bugs around fee accounting, ERC-4626 non-conformance, and phantom balance.
2. **TWAP hardened:** R-3 per-block dedup closes the most critical V2 finding (single-block buffer flooding). TWAP manipulation now requires multi-block sustained price distortion.
3. **Slippage bounded:** `setMaxSlippageBps` enforces 10-500 bps range with event emission.
4. **Simpler withdraw path:** Standard ERC-4626 withdraw + nonReentrant + TWAP. No fee deduction logic means fewer accounting edge cases.

### 7.2 What Remains Concerning

1. **Asymmetric slippage protection** (V3-1): Add is protected, remove is not. This is the single largest remaining risk. Any LP removal (rebalance LP-off, emergency withdraw, user withdraw triggering `beforeWithdraw`) is sandwichable with no bound. The decision to skip removal slippage was intentional to avoid bricking, but it leaves a real extraction vector.

2. **L2 TWAP economics** (V3-2): On L2s with 2-second blocks, cross-block TWAP filling takes only ~20 seconds. The cost of manipulation is dramatically lower than on L1. If deploying to L2, the TWAP window should be evaluated for sufficiency.

3. **No time-based keeper rate limit** (V3-3): A compromised keeper can make unlimited calls per block. Adding a `lastPushTimestamp` with a minimum interval (e.g., 1 hour) would limit ratcheting velocity.

### 7.3 Deployment Recommendation

**Risk Level: MEDIUM -- Acceptable for mainnet with $10K deposit cap.**

Rationale:
- At the current $10K cap, worst-case extractable value per event is ~$500 (sandwich removal)
- TWAP manipulation is unprofitable on L1 for this vault size
- Fee removal eliminated 3+ medium-severity findings from V2
- The remaining risks (removal slippage, keeper compromise) are bounded and monitorable
- Virtual shares (1e6 offset) protect against inflation attacks
- Two-step ownership prevents accidental key transfer
- Emergency withdraw + pause provides a circuit breaker

**Before increasing deposit cap beyond $100K:**
1. Add slippage check on `_executeRemoveLiquidity()` with an emergency bypass flag
2. Add per-hour rate limiting to `pushVolEstimate()`
3. If deploying to L2: increase `TWAP_WINDOW` to 30+ and/or add `block.number` dedup
4. Consider a timelock on admin parameter changes (`setLPRange`, `setTwapThreshold`, `setMaxSlippageBps`)

**Monitoring requirements for mainnet:**
- Watch `KeeperVolPushed` events for anomalous vol values
- Watch `Rebalanced` events for large totalAssets drops (sandwich indicator)
- Alert on `PauseUpdated` and `OwnershipTransferStarted` events
- Track share price (via `convertToAssets(1e6)`) for unexpected movements
