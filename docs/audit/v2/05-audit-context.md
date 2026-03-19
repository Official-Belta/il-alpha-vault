# IL Alpha Vault — Audit Context v2 (Post-Fix)

Date: 2026-03-20
Scope: All contracts in `contracts/src/`
Previous version: `docs/audit/05-audit-context.md`

---

## 1. System Architecture (Updated)

### 1.1 Component Diagram

```
                              +---------------------------------------------+
                              |            Uniswap V4 PoolManager            |
                              |  (singleton, holds all pool state & funds)   |
                              +------+------------------+--------------------+
                                     | afterSwap()      | unlock() callback
                                     | afterInitialize() | modifyLiquidity()
                                     v                  | swap() / settle()
                              +-----------------------+ |
                              |     ILAlphaHook       | |
                              |                       | |
                              | * VolOracle (EWMA)    | |
                              | * PoolState           | |
                              | * LP Toggle           | |
                              | * Volume EMA          | |
                              | * TWAP Accumulator    |<--- NEW (H-1 fix)
                              |   - TickObservation[10]|
                              |   - circular buffer    |
                              |   - 1hr recency weight |
                              +-----------+-----------+
                                          | isLPActive()
                                          | getPoolStrategy()
                                          | getTwapTick()  <--- NEW
                                          v
                              +--------------------------+
                              |     ILAlphaVault         |
                              |  (ERC-4626 + IUnlock)    |
                              |                          |
                              | * deposit/withdraw       |
                              | * rebalance (add/remove) |
                              | * TWAP check (real TWAP) |<--- UPGRADED (H-1)
                              | * Slippage checker       |<--- NEW (H-2)
                              | * Withdrawal fee deduct  |<--- FIXED (C-1)
                              | * mint() guards          |<--- FIXED (C-2)
                              | * Pool key safety        |<--- FIXED (C-3)
                              | * Single-token totalAssets|<-- FIXED (H-7)
                              +------------+-------------+
                                           | extends
                                           v
                              +--------------------------+
                              |       BaseVault          |
                              |  (ERC-4626 + virtual     |
                              |   shares/assets offset)  |
                              +------------+-------------+
                                           | extends
                         +-----------------+-----------------+
                         v                 v                 v
                  +-------------+   +-------------+   +-----------+
                  |AlwaysLPVault|   |  HODLVault  |   |ILAlphaVault|
                  | (control)   |   | (control)   |   | (main)    |
                  +-------------+   +-------------+   +-----------+

                  +--------------+
                  |  SwapHelper  |  (testnet utility, owner-gated)
                  |  IUnlock     |  executes swaps / adds liquidity
                  +--------------+

External actors:
  [User]   -> deposit/withdraw on Vault
  [Keeper] -> rebalance(), pushVolEstimate(), triggerEvaluation()
  [Owner]  -> admin params, emergency withdraw, pause
  [MEV]    -> swaps on PoolManager trigger afterSwap hook
```

### 1.2 New Components Added Since v1

| Component | Contract | Purpose | Fixes |
|---|---|---|---|
| **TWAP Tick Accumulator** | ILAlphaHook (lines 96-115, 447-481) | Circular buffer of 10 tick observations, recency-weighted, 1-hour window | H-1: replaces weak lastTick comparison with real TWAP |
| **Slippage Checker** | ILAlphaVault (lines 373-377) | Bounds total cost of addLiquidity vs expected assets | H-2: prevents LP at manipulated price |
| **Fee Deduction in withdraw/redeem** | ILAlphaVault (lines 325-370) | Full override of withdraw() and redeem() with actual fee deduction before transfer | C-1: fee now deducted from user, not diluted from vault |
| **mint() Guards** | ILAlphaVault (lines 183-196) | Applies same checks as deposit() to mint() path | C-2: prevents bypass via mint() |
| **Pool Key Safety** | ILAlphaVault (lines 479-488) | Prevents setPoolKey when LP deployed; validates asset match | C-3: prevents stranded funds |
| **Keeper Rate Limit Tightening** | ILAlphaHook (lines 377-396) | 2x rate limit (was uncapped from zero); zero baseline capped to 1e18 | H-4: limits compromised keeper damage |
| **Single-Token totalAssets** | ILAlphaVault (lines 148-168) | Only counts LP value in the vault's asset token | H-7: prevents cross-token valuation errors |

### 1.3 Data Flow: Updated Withdraw Path

```
WITHDRAW (C-1 FIX - fully overridden):
  User -> withdraw(assets, receiver, owner_)
    -> nonReentrant (H-5)
    -> _checkTWAP() using real TWAP accumulator (H-1)
    -> _ensureIdle(assets): pull LP if needed
    -> fee = assets * withdrawalFeeBps / 10_000
    -> accumulatedFees += fee
    -> shares = previewWithdraw(assets)
    -> allowance check (if msg.sender != owner_)
    -> _burn(owner_, shares)
    -> emit Withdraw(...)
    -> asset.safeTransfer(receiver, assets - fee)  <-- user gets assets MINUS fee

REDEEM (C-1 FIX - fully overridden):
  User -> redeem(shares, receiver, owner_)
    -> nonReentrant (H-5)
    -> _checkTWAP()
    -> allowance check
    -> assets = previewRedeem(shares)
    -> require(assets != 0)
    -> _ensureIdle(assets)
    -> fee = assets * withdrawalFeeBps / 10_000
    -> accumulatedFees += fee
    -> _burn(owner_, shares)
    -> emit Withdraw(...)
    -> asset.safeTransfer(receiver, assets - fee)
```

---

## 2. Threat Model Re-Evaluation (Post-Fix)

### 2.1 H-1: Is the TWAP Now Effective Against Flash Loans?

**Mechanism:** The TWAP accumulator stores 10 `TickObservation` entries in a circular buffer. Each observation records `(tick, timestamp)`. `getTwapTick()` computes a recency-weighted average: observations are weighted by `(3600 - age)`, and any observation older than 1 hour is discarded.

**Flash Loan Analysis:**

An attacker who manipulates price in block N faces the following constraints:

1. **Can the attacker fill the buffer in one block?** YES, in theory. The `_recordTickObservation()` function is called on every `afterSwap`. If the attacker executes 10+ swaps within a single block, they can overwrite the entire circular buffer. Each swap in the same block gets `timestamp = block.timestamp`, so all 10 entries would have the same timestamp and the same high recency weight.

2. **However, the vol oracle has same-block protection:** `_updateVolOracle()` returns early when `elapsed == 0` (line 301). This means same-block swaps after the first do NOT update EWMA variance. But they DO record tick observations (line 265 is called unconditionally).

3. **Attack scenario:**
   - Attacker flash-borrows, executes 10 swaps in one block to fill TWAP buffer with manipulated ticks
   - All observations have the same `block.timestamp`, so all have equal weight
   - `getTwapTick()` returns the manipulated average
   - Attacker deposits/withdraws at manipulated share price
   - `_checkTWAP()` passes because TWAP itself is manipulated

**Verdict: PARTIALLY EFFECTIVE.** The TWAP is effective against cross-block manipulation (attacker must sustain manipulation for multiple blocks, which is expensive). It is NOT effective against single-block buffer flooding. The buffer can be filled in one transaction with 10 swaps.

**Residual Risk: MEDIUM-HIGH.** A flash loan attacker can:
- Execute 10 small swaps to fill the buffer
- Execute 1 large swap to move the price
- The TWAP now reflects the manipulated price
- Deposit or withdraw at favorable rates

**Recommendation:** Add a minimum observation spacing requirement (e.g., at most 1 observation per block, using `block.number` tracking). Alternatively, require observations from at least N distinct blocks before TWAP is considered valid.

### 2.2 Is the Withdrawal Fee Now Correctly Deducted?

**Before (v1 Bug):** Fee was calculated in `beforeWithdraw()` and added to `accumulatedFees`, but the ERC4626 base still transferred the full `assets` amount to the user. The fee diluted remaining depositors.

**After (C-1 Fix):** `withdraw()` and `redeem()` are fully overridden. The flow is now:

```
withdraw(assets):
  shares = previewWithdraw(assets)   // shares needed to get `assets` worth
  fee = assets * feeBps / 10_000
  _burn(shares)
  transfer(receiver, assets - fee)   // user gets less than `assets`
```

**Accounting Analysis:**

| Step | totalSupply change | totalAssets change | Share price effect |
|---|---|---|---|
| Before withdraw | S | T | T/S |
| After _burn | S - shares | T | -- |
| After transfer | S - shares | T - (assets - fee) | -- |
| Net | S - shares | T - assets + fee | (T - assets + fee) / (S - shares) |

The fee remains in `totalAssets()` (since `accumulatedFees` is tracked separately but the tokens stay in the vault's balance). This means the fee slightly benefits remaining depositors via a higher share price, which is the correct economic behavior.

**Verdict: CORRECTLY FIXED.** The fee is now genuinely deducted from the withdrawing user's proceeds. The `accumulatedFees` counter tracks claimable fees for the owner, and `claimFees()` (line 524-533) has a safety check: it only transfers `min(fees, available_balance)`.

**Remaining Concern:** The `Withdraw` event (line 345, 368) emits `assets` as the full pre-fee amount, not the actual transferred amount (`assets - fee`). This is technically ERC-4626 compliant (the event describes the "assets equivalent" of shares burned), but off-chain integrators may misinterpret the actual transfer amount. This is a LOW-severity informational issue.

### 2.3 Is Keeper Compromise Impact Reduced with 2x Rate Limit?

**Before (v1):** `pushVolEstimate()` had a rate limit of effectively unlimited from zero (`maxExternal = type(uint128).max` when `ewmaVar == 0`). Even from non-zero, the 4x cap allowed compounding: `4^N` growth over N calls.

**After (H-4 Fix):**
```solidity
uint256 maxExternal = currentVar == 0 ? uint256(1e18) : currentVar * 2;
```

**Analysis:**
- From zero: Keeper can push at most `1e18` as external var. After blending 50/50 with current (0), result = `0.5e18`. Next call: max push = `0.5e18 * 2 = 1e18`, blended = `(0.5e18 + 1e18) / 2 = 0.75e18`. Growth is logarithmic, not exponential.
- From non-zero: Maximum compounding per call is `currentVar * 2`, blended = `(current + current*2) / 2 = 1.5 * current`. So each call can increase var by at most 50%. After N calls: `1.5^N * initial`. To reach 100x from initial, need `1.5^N = 100` -> `N = log(100)/log(1.5) = 11.4` calls.
- Compared to v1 (4x cap, unlimited from zero): the compounding rate is significantly reduced (1.5x vs 3x per call from non-zero).

**Verdict: SIGNIFICANTLY IMPROVED.** The keeper can no longer set arbitrary initial vol from zero. Compounding is slower (1.5x/call vs 3x/call). An attacker needs ~11 rapid calls to 100x the variance, and the EWMA decay (lambda=0.94) simultaneously pulls variance back toward true value between swaps.

**Residual Risk: LOW-MEDIUM.** A compromised keeper can still degrade strategy quality over multiple calls, but cannot cause catastrophic damage in a single action. The 24-hour cooldown on LP toggle limits how often wrong decisions can be forced.

---

## 3. New Mechanisms Deep Dive

### 3.1 TWAP Tick Accumulator

**Implementation (ILAlphaHook lines 96-481):**

```
Constants:
  TWAP_WINDOW = 10 (number of observations)

Storage:
  tickObservations[poolId][10]  -- circular buffer of (tick, timestamp)
  observationIndex[poolId]      -- current write position

Recording (_recordTickObservation):
  - Called on every afterSwap
  - Writes (currentTick, block.timestamp) at current index
  - Advances index modulo 10

Reading (getTwapTick):
  - Iterates all 10 slots
  - Skips zero-timestamp entries (uninitialized)
  - Skips entries older than 3600 seconds (1-hour window)
  - Weights each observation by (3600 - age): newer = higher weight
  - Returns weightedSum / totalWeight, or lastTick as fallback
```

**Is 10 observations sufficient?**

For a pool with moderate swap activity (1 swap per ~6 minutes), the buffer covers 1 hour. For high-activity pools (1 swap per minute), the buffer covers only 10 minutes and older observations are overwritten. For low-activity pools (1 swap per hour), only 1-2 observations may be within the 1-hour window.

| Pool Activity | Buffer Coverage | TWAP Quality |
|---|---|---|
| 1 swap/minute | 10 minutes | Poor: short window, easy to fill with manipulated data |
| 1 swap/6 minutes | 1 hour | Good: covers full window |
| 1 swap/30 minutes | 5 hours (but only 2 in window) | Weak: few data points |
| 1 swap/hour | 10 hours (but only 1 in window) | Very weak: falls back to lastTick |

**Key Weakness: No per-block deduplication.** An attacker can record 10 observations in a single block by executing 10 swaps. All observations get the same timestamp and thus equal weight. This allows single-block TWAP manipulation (see Section 2.1).

**Recency Weighting Analysis:** The linear weight `(3600 - age)` gives a fresh observation (age=0) 3600x the weight of an observation at age=3599. This heavily favors recent data, which is good for responsiveness but bad for manipulation resistance. A single fresh manipulated observation can dominate the TWAP if other observations are near the 1-hour boundary.

**Recommendation:**
1. Track `block.number` and skip duplicate-block recordings, or cap at 1 observation per block
2. Consider increasing TWAP_WINDOW to 20-30 for better coverage on active pools
3. Consider using cumulative tick*time accumulator (Uniswap V3 oracle style) instead of discrete samples

### 3.2 Slippage Protection

**Implementation (ILAlphaVault line 373-377):**

```solidity
function _checkSlippage(int128 d0, int128 d1, uint256 expected) internal view {
    uint256 actualCost = (d0 < 0 ? uint256(uint128(-d0)) : 0)
                       + (d1 < 0 ? uint256(uint128(-d1)) : 0);
    uint256 maxCost = expected + (expected * maxSlippageBps) / 10_000;
    if (actualCost > maxCost) revert SlippageExceeded();
}
```

**Coverage:**
- `addLiquidity`: YES -- checked in `_executeAddLiquidity()` (line 274)
- `removeLiquidity`: **NO** -- `_executeRemoveLiquidity()` has no slippage check

**RemoveLiquidity Gap Analysis:**

When the vault removes liquidity, it calls `modifyLiquidity()` with a negative `liquidityDelta`. The returned `BalanceDelta` tells the vault how many tokens it receives back. If the pool price has been manipulated, the vault may receive mostly one token and very little of the other.

The impact depends on `totalAssets()`:
- If `totalAssets()` only counts the asset token (H-7 fix), then a price manipulation that shifts value into the non-asset token would reduce `totalAssets()` and thus the share price
- After removal, the vault holds idle tokens; the non-asset token is "stranded" until manually handled

**Severity: MEDIUM.** While removeLiquidity slippage is less exploitable (the attacker can't directly profit from the vault receiving fewer tokens), it can cause value leakage. The vault may receive an unfavorable token split, and the non-asset token has no swap path back.

**Recommendation:** Add slippage check on removeLiquidity, comparing received asset-token amount against expected value from `_getDeployedLPValue()`.

### 3.3 Fee Deduction: ERC-4626 Consistency

**withdraw() (line 329-347):**
```
User requests `assets` worth of withdrawal.
shares = previewWithdraw(assets)  -- how many shares needed
Fee deducted: user receives `assets - fee`
Shares burned: shares (based on full `assets`)
```

**Inconsistency:** The user burns shares worth `assets`, but receives `assets - fee`. This means the user is overcharged in shares relative to what they receive. From the user's perspective, they request X assets, lose X-worth-of-shares, but only get X*(1-feeBps/10000). This is a valid "exit fee" model.

**redeem() (line 351-370):**
```
User redeems `shares`.
assets = previewRedeem(shares)  -- asset value of those shares
Fee deducted: user receives `assets - fee`
Shares burned: shares (the full amount)
```

**Consistency check:** Both paths deduct fee from the gross asset amount. The fee token stays in the vault, increasing effective totalAssets for remaining holders. This is consistent.

**ERC-4626 Compliance:**
- `previewWithdraw(assets)` returns shares needed to withdraw `assets` worth. The actual transfer is `assets - fee`. The standard says "MUST return as close to and no more than the exact amount of Vault shares that would be burned." Since the user is burning `previewWithdraw(assets)` shares to get `assets - fee`, the preview overestimates the user's output. This is **non-compliant** with strict ERC-4626 semantics.
- Per EIP-4626: `withdraw(assets)` should transfer exactly `assets` to the receiver. Transferring `assets - fee` violates this.
- **Standard-compliant alternative:** `previewWithdraw` should account for the fee, so `withdraw(assets)` burns more shares but transfers exactly `assets`. Or, document that `assets` represents the gross amount before fees.

**Severity: LOW (informational).** Functionally correct (users pay a fee, vault accounting is sound), but technically non-compliant with ERC-4626 spec. This could break composability with ERC-4626 routers, aggregators, or other contracts that expect `withdraw(X)` to deliver exactly X tokens.

---

## 4. Updated Risk Matrix

### 4.1 Resolved Findings from v1

| v1 # | Finding | v1 Severity | Fix Applied | Residual Risk |
|---|---|---|---|---|
| 5.4 | Rebalance has no TWAP/price check | HIGH | H-2: slippage check on addLiquidity | LOW-MEDIUM (removeLiquidity still unprotected) |
| 5.5 | Withdrawal fee not deducted from user | MEDIUM | C-1: full withdraw/redeem override | RESOLVED (minor ERC-4626 spec deviation) |
| 5.6 | LP range change strands liquidity | MEDIUM | C-3: setPoolKey blocked when LP deployed | RESOLVED for pool key; setLPRange on hook still not gated |
| 5.7 | No slippage protection on LP operations | MEDIUM | H-2: slippage check on addLiquidity | LOW-MEDIUM (removeLiquidity unprotected) |
| 5.2 | EWMA can be gamed over ~11 blocks | MEDIUM | Unchanged (inherent EWMA property) | MEDIUM |
| 5.3b | Keeper unlimited vol from zero | MEDIUM | H-4: cap zero baseline to 1e18, 2x limit | LOW-MEDIUM |
| 3.4 | TWAP uses lastTick not true TWAP | MEDIUM | H-1: real TWAP accumulator | LOW-MEDIUM (buffer flooding risk) |
| 5.8 | AlwaysLPVault double-counts assets | LOW | H-6: removed deployedAssets tracking | RESOLVED |

### 4.2 New/Remaining Findings (v2)

| # | Finding | Severity | Location | Description |
|---|---|---|---|---|
| V2-1 | TWAP buffer can be filled in single block | MEDIUM-HIGH | ILAlphaHook._recordTickObservation() | No per-block deduplication; 10 swaps in 1 tx overwrites entire buffer, defeating TWAP protection |
| V2-2 | No slippage check on removeLiquidity | MEDIUM | ILAlphaVault._executeRemoveLiquidity() | Vault accepts whatever token split pool returns; price manipulation before removal causes value leakage |
| V2-3 | withdraw() transfers less than `assets` parameter | LOW | ILAlphaVault.withdraw() | ERC-4626 spec says withdraw(X) should transfer X; actual transfer is X-fee. Breaks composability assumptions |
| V2-4 | TWAP recency weight dominated by fresh observations | LOW | ILAlphaHook.getTwapTick() | Linear weight (3600-age) gives 3600:1 ratio between newest and oldest observation; single fresh manipulation dominates |
| V2-5 | setLPRange on hook not gated by vault LP status | LOW | ILAlphaHook.setLPRange() | Owner can change tick range while vault has deployed liquidity; removal would use new range, not old range where liquidity sits |
| V2-6 | TWAP fallback to lastTick on empty buffer | LOW | ILAlphaHook.getTwapTick() | When no valid observations exist, returns lastTick (same as v1 behavior), which can be the manipulated tick |
| V2-7 | EWMA oracle still gameable over ~11 blocks | MEDIUM | ILAlphaHook._updateVolOracle() | Unchanged from v1; inherent EWMA property. Attacker cost is swap fees + slippage per manipulation swap |
| V2-8 | getVaultMetrics deploys sum both tokens | INFO | ILAlphaVault.getVaultMetrics() | `deployedValue = v0 + v1` in view function sums both tokens (unlike totalAssets which correctly uses single token). Only affects off-chain display |

### 4.3 Risk Summary by Adversary (Post-Fix)

| Adversary | v1 Max Impact | v2 Max Impact | Key Improvement |
|---|---|---|---|
| **Flash Loan Attacker** | HIGH: manipulate rebalance price, drain via deposit/withdraw | MEDIUM-HIGH: can still flood TWAP buffer in 1 block | Slippage check on addLiquidity limits rebalance manipulation; TWAP buffer flooding is new residual |
| **Compromised Keeper** | MEDIUM: unlimited vol injection from zero, 4^N compounding | LOW-MEDIUM: capped to 1e18 from zero, 1.5x compounding | H-4 rate limit significantly reduces damage ceiling |
| **MEV Bot** | MEDIUM: sandwich rebalance with no slippage protection | LOW-MEDIUM: slippage check on addLiquidity, TWAP on deposit/withdraw | Slippage bound limits sandwich profit; removeLiquidity still exposed |
| **Malicious User** | MEDIUM: bypass fee via accounting bug, exploit mint() without guards | LOW: fees correctly deducted, mint() guarded | C-1 and C-2 close the main user-exploitable paths |

### 4.4 Priority Remediation Recommendations

1. **V2-1 (MEDIUM-HIGH):** Add per-block deduplication to tick observations. Track `lastRecordedBlock[poolId]` and skip recording if `block.number == lastRecordedBlock`. This is a single-SSTORE addition (~5K gas) that closes the single-block flooding attack.

2. **V2-2 (MEDIUM):** Add slippage check on removeLiquidity. Compare the received asset-token amount against `_getDeployedLPValue()` with a tolerance of `maxSlippageBps`.

3. **V2-5 (LOW):** Gate `setLPRange()` on hook: either revert if any vault has deployed liquidity (requires vault registry), or track the range used when liquidity was added and use that range for removal.

4. **V2-3 (LOW):** Either adjust `previewWithdraw()` to account for the fee (so the shares burned match the net transfer), or document the deviation from ERC-4626 spec clearly for integrators.
