# IL Alpha Vault — Audit Context (Trail of Bits Style)

Date: 2026-03-20
Scope: All contracts in `contracts/src/`

---

## 1. System Architecture

### 1.1 Component Diagram

```
                              ┌─────────────────────────────────────────────┐
                              │            Uniswap V4 PoolManager          │
                              │  (singleton, holds all pool state & funds)  │
                              └──────┬──────────────────┬──────────────────┘
                                     │ afterSwap()      │ unlock() callback
                                     │ afterInitialize() │ modifyLiquidity()
                                     ▼                  │ swap() / settle()
                              ┌──────────────┐          │
                              │ ILAlphaHook  │          │
                              │              │          │
                              │ • VolOracle  │          │
                              │ • PoolState  │          │
                              │ • LP Toggle  │          │
                              │ • Volume EMA │          │
                              └──────┬───────┘          │
                                     │ isLPActive()     │
                                     │ getPoolStrategy() │
                                     ▼                  ▼
                              ┌──────────────────────────┐
                              │     ILAlphaVault         │
                              │  (ERC-4626 + IUnlock)    │
                              │                          │
                              │ • deposit/withdraw       │
                              │ • rebalance (add/remove) │
                              │ • TWAP check             │
                              │ • withdrawal fees        │
                              └──────────┬───────────────┘
                                         │ extends
                                         ▼
                              ┌──────────────────────────┐
                              │       BaseVault          │
                              │  (ERC-4626 + virtual     │
                              │   shares/assets offset)  │
                              └──────────┬───────────────┘
                                         │ extends
                         ┌───────────────┼───────────────┐
                         ▼               ▼               ▼
                  ┌─────────────┐ ┌─────────────┐ ┌───────────┐
                  │AlwaysLPVault│ │  HODLVault  │ │ILAlphaVault│
                  │ (control)   │ │ (control)   │ │ (main)    │
                  └─────────────┘ └─────────────┘ └───────────┘

                  ┌──────────────┐
                  │  SwapHelper  │  (testnet utility, owner-gated)
                  │  IUnlock     │  executes swaps / adds liquidity
                  └──────────────┘

External actors:
  [User]   → deposit/withdraw on Vault
  [Keeper] → rebalance(), pushVolEstimate(), triggerEvaluation()
  [Owner]  → admin params, emergency withdraw, pause
  [MEV]    → swaps on PoolManager trigger afterSwap hook
```

### 1.2 Data Flow: Deposit → Rebalance → LP → Withdraw Lifecycle

```
DEPOSIT:
  User → deposit(assets, receiver)
    → whenNotPaused, nonReentrant
    → DepositTooSmall check (>= 1e6)
    → DepositCap check
    → _checkTWAP() — revert if spot deviates from oracle tick
    → BaseVault.deposit() → ERC4626 mint shares, pull assets
    → Assets sit idle in vault

REBALANCE (anyone can call):
  Caller → rebalance()
    → whenNotPaused, nonReentrant
    → hook.isLPActive(poolKey) — reads hook's PoolState.isLPActive
    → if shouldLP && deployedLiquidity == 0:
        → _addLiquidity(idleAssets)
        → poolManager.unlock() → unlockCallback() → _executeAddLiquidity()
            → getSlot0 for current price
            → hook.getPoolStrategy() for tick range
            → LiquidityAmounts.getLiquidityForAmounts()
            → poolManager.modifyLiquidity(+liquidity)
            → settle negative deltas (transfer tokens to PM)
            → take positive deltas (fee credits)
            → deployedLiquidity += liquidity
    → if !shouldLP && deployedLiquidity > 0:
        → _removeLiquidity()
        → poolManager.unlock() → unlockCallback() → _executeRemoveLiquidity()
            → poolManager.modifyLiquidity(-deployedLiquidity)
            → take back tokens
            → deployedLiquidity = 0

HOOK SIGNAL (automatic, on every swap):
  Swap on pool → PoolManager → afterSwap()
    → volume spike check (absAmount > 3x ewmaVolume → emergency LP off, bypass cooldown)
    → update volume EWMA
    → update vol oracle (EWMA variance from tick deltas)
    → if cooldown expired: _evaluateLPToggle()
        → feeYield = poolFee * ewmaVolume / 1_000_000
        → ilCost = 0.5 * ewmaVar * concentration / 1e36
        → shouldBeActive = feeYield > ilCost
        → toggle if changed

WITHDRAW:
  User → withdraw(assets, receiver, owner)  [inherited from ERC4626]
    → beforeWithdraw() override:
        → _checkTWAP()
        → deduct withdrawal fee (0.1% default)
        → if idle < assets && deployedLiquidity > 0 → _removeLiquidity()
    → ERC4626 burns shares, transfers assets
```

### 1.3 Trust Boundaries

| Boundary | Trusts | Trusted By |
|---|---|---|
| **PoolManager** | Hook (afterSwap only returns selector) | Vault (holds all pool funds), Hook |
| **ILAlphaHook** | PoolManager (for callbacks), Owner (config), Keeper (vol push) | Vault (isLPActive signal, tick range) |
| **ILAlphaVault** | Hook (strategy signal), PoolManager (LP operations), Owner (admin), BaseVault (share math) | Users (deposits) |
| **BaseVault** | Solmate ERC4626 (share math base) | All vault subclasses |
| **Keeper** | Trusted by Hook (vol push, trigger) and implicitly by Vault (rebalance is permissionless but follows hook signal) | Trusted by Owner to operate correctly |
| **Owner** | Omnipotent over Hook config and Vault admin | Trusted by all users |

---

## 2. Threat Model

### 2.1 Asset Inventory

| Asset | Location | Value | Risk |
|---|---|---|---|
| User deposits (idle) | Vault contract balance | Up to depositCap (default 10K USDC) | Theft, locked funds |
| LP position tokens | PoolManager (via vault's liquidity) | Variable, up to full deposit value | IL, manipulation, rug |
| Accumulated fees | Vault `accumulatedFees` | Small fraction of withdrawals | Theft by owner compromise |
| ERC-4626 shares | Vault (user balances) | Represents claim on assets | Dilution, inflation attack |
| LP strategy signal | Hook `isLPActive` flag | Controls fund deployment | Manipulation → forced IL |
| Vol oracle state | Hook `volOracles` mapping | Drives strategy decisions | Manipulation → wrong decisions |

### 2.2 Adversary Profiles

#### A. Malicious User
- **Goal:** Extract more value than deposited
- **Capabilities:** Deposit, withdraw, call rebalance(), execute swaps
- **Attack surfaces:**
  - ERC-4626 share inflation/donation attack (mitigated by virtual shares)
  - Sandwich vault rebalance: front-run rebalance with swap to move price, back-run to profit
  - Manipulate totalAssets() between deposit and withdraw
  - Call rebalance() at disadvantageous times
  - Flash loan + deposit + rebalance + withdraw in one tx (partially mitigated by TWAP check)

#### B. Compromised Keeper
- **Goal:** Drain vault or manipulate strategy
- **Capabilities:** pushVolEstimate(), triggerEvaluation(), rebalance()
- **Attack surfaces:**
  - Push false vol to force LP toggle (rate-limited to 4x current var when current is 0 — **BUG: when ewmaVar == 0, maxExternal = type(uint128).max, no rate limiting**)
  - Repeatedly push vol up over multiple calls (compounding: each call can 4x, so 4^n growth)
  - triggerEvaluation() to force LP toggle at bad times (cooldown-gated)
  - Cannot directly steal funds — no transfer/withdrawal capability

#### C. MEV Bot
- **Goal:** Extract value from vault operations
- **Capabilities:** Observe mempool, front-run/back-run, bundle transactions
- **Attack surfaces:**
  - Sandwich rebalance() calls (vault adds/removes liquidity at predictable price)
  - Sandwich deposits/withdrawals (TWAP check provides some protection)
  - JIT liquidity around vault's LP range
  - Trigger afterSwap to manipulate vol oracle via large swaps

#### D. Flash Loan Attacker
- **Goal:** Manipulate price/oracle for profit
- **Capabilities:** Borrow unlimited capital for one transaction
- **Attack surfaces:**
  - Move spot price far from TWAP → blocked by _checkTWAP() for deposits/withdrawals
  - Large swap to spike volume → triggers emergency LP off (SPIKE_MULTIPLIER = 3x)
  - Manipulate sqrtPriceX96 used in _getDeployedLPValue() during rebalance
  - **Key gap:** rebalance() does NOT call _checkTWAP() — price can be manipulated during LP add

---

## 3. Key Mechanisms Deep Dive

### 3.1 EWMA Volatility Oracle

**Mathematical Model:**
```
tickDelta = currentTick - lastTick
squaredReturn = tickDelta^2 * 1e18
squaredReturn_hourly = squaredReturn * 3600 / elapsed
newVar = lambda * oldVar + (1 - lambda) * squaredReturn_hourly
```

**Parameters:**
- lambda: 9400 bps (0.94) default, range [5000, 9900]
- Decay half-life at lambda=0.94: ~11 observations (ln(0.5)/ln(0.94) ≈ 11.2)

**Correctness Analysis:**
- Uses tick-space squared returns as variance proxy — mathematically sound since tick ≈ log(price) / log(1.0001)
- Time normalization to per-hour via `squaredReturn * 3600 / elapsed` — correct for converting per-observation to per-hour
- Overflow: max tickDelta = 887,272 (MAX_TICK range). 887272^2 * 1e18 = ~7.87e29, fits uint256. Safe.
- Capped to uint128 to fit packed struct — reasonable, uint128 max ≈ 3.4e38

**Manipulation Resistance:**
- WEAK: A single large swap can inject arbitrary variance. No smoothing beyond EWMA decay.
- Same-block protection: `elapsed == 0` returns early — prevents multiple manipulations in one block
- **Vulnerability:** Attacker can slowly game EWMA over ~11 blocks (half-life). Each block's swap contributes (1-lambda)=6% weight. After 20 blocks, old data is <30% of EWMA.
- Keeper push is rate-limited to 4x current var, but **when ewmaVar is 0, limit is uint128.max** — keeper can set arbitrary initial vol
- annualizedVol computation `hourlyVar * 8760` is a view function only (not used in decisions)

### 3.2 LP Toggle Logic

**Decision Formula:**
```
feeYield = poolFee * ewmaVolume / 1_000_000
ilCost = GAMMA_FACTOR * ewmaVar * concentration / 1e36
concentration = 10_000 * 1e18 / tickRange

shouldBeActive = feeYield > ilCost
```

**Analysis:**
- Fee yield is proportional to volume and fee tier — reasonable proxy
- IL cost uses gamma exposure model (0.5 * sigma^2 * concentration) — standard options-inspired IL estimate
- Concentration factor inversely proportional to tick range — correct (tighter range = more IL per unit variance)
- **Units concern:** feeYield units = (bps_hundredths * volume_token_scaled) / 1e6. ilCost units = (0.5e18 * variance_scaled * concentration) / 1e36. These should be comparable for the decision to be valid — needs verification that units actually match.
- **No hysteresis:** Toggle flips on any crossing of feeYield == ilCost boundary. Rapid toggling near boundary is prevented only by 24-hour cooldown.

### 3.3 ERC-4626 Share Accounting

**Virtual Shares Defense (BaseVault):**
```
VIRTUAL_SHARES = 1e6
VIRTUAL_ASSETS = 1e6

convertToShares(assets) = assets * (totalSupply + 1e6) / (totalAssets + 1e6)
convertToAssets(shares) = shares * (totalAssets + 1e6) / (totalSupply + 1e6)
```

**Analysis:**
- Effective against first-depositor inflation attack: attacker would need to donate >1e6 asset units to meaningfully shift the exchange rate, which costs real money
- For USDC (6 decimals), VIRTUAL_ASSETS = 1e6 = 1 USDC — provides meaningful protection
- Rounding: uses mulDivDown for conversions (favors vault on deposits, favors user on withdrawals). previewMint and previewWithdraw use mulDivUp (favors vault) — correct ERC-4626 compliance
- **Note:** totalAssets() includes real-time LP valuation via _getDeployedLPValue(), which reads sqrtPriceX96 from PoolManager. This creates a dependency on spot price for share pricing.

### 3.4 TWAP Manipulation Check

**Implementation (`_checkTWAP`):**
```solidity
int24 deviation = |spotTick - lastOracleTick|;
if (deviation > twapThreshold) revert PriceManipulated();
```

**Effectiveness:**
- **NOT a real TWAP.** Uses hook's `lastTick` (the tick at the previous swap) as a reference, not a time-weighted average.
- Provides protection against same-block manipulation if there was a prior swap in a different block
- **Weakness:** If the attacker's swap IS the most recent swap, `lastTick` already reflects the manipulated price. The _next_ operation would see the manipulated tick as the reference.
- **Bypass:** Attacker can gradually move price across multiple blocks, each within threshold (500 ticks ≈ 5%), to accumulate a large deviation
- Only checked on deposit() and beforeWithdraw(), **NOT on rebalance()** — a significant gap

### 3.5 Cooldown Mechanism

**Implementation:**
- COOLDOWN_SECONDS = 24 hours
- After any LP toggle, `lastToggleTime` is set
- Next toggle requires `block.timestamp >= lastToggleTime + COOLDOWN_SECONDS`

**Bypass Conditions:**
1. **Volume spike:** If `absAmount > 3x ewmaVolume`, LP is turned off regardless of cooldown (emergency off only, never emergency on)
2. **Keeper triggerEvaluation():** Respects cooldown (reverts if active)
3. **First toggle:** `lastToggleTime` is initialized to 0, so the first toggle has no cooldown
4. **Owner setLPRange():** No cooldown. Changing tick range could indirectly affect LP decisions.

---

## 4. External Dependencies

### 4.1 Uniswap V4 PoolManager

| Function Used | By | Trust Assumption |
|---|---|---|
| `getSlot0()` | Vault, Hook | Returns accurate current pool state |
| `modifyLiquidity()` | Vault | Correctly adds/removes liquidity, returns accurate deltas |
| `unlock()` / callback | Vault | Calls back exactly once, passes data faithfully |
| `swap()` | SwapHelper | Executes swap correctly |
| `sync()` / `settle()` / `take()` | Vault, SwapHelper | Token accounting is correct |
| Hook callbacks (afterSwap, afterInitialize) | Hook | Called exactly when expected, with correct parameters |

**Risk:** PoolManager is the singleton that holds ALL pool funds. A bug in PoolManager affects all protocols. This is Uniswap-audited infrastructure assumed to be correct.

**Callback Reentrancy Model:** V4 uses `unlock()` which allows the caller to perform arbitrary operations within the callback. The vault's `_locked` reentrancy guard protects against reentrant deposits/withdrawals/rebalances, but cross-contract reentrancy through the hook's afterSwap during a vault's modifyLiquidity is possible — see Section 5.

### 4.2 Solmate Library

| Component | Usage | Version Risk |
|---|---|---|
| `ERC4626` | BaseVault inherits | Well-audited, standard implementation |
| `ERC20` | Token interface | Standard |
| `SafeTransferLib` | Token transfers in Vault | Handles non-standard return values |
| `FixedPointMathLib` | mulDivDown, mulDivUp | Standard math library |

**Trust:** Solmate is widely audited and battle-tested. Low risk.

### 4.3 Uniswap V4 Test Utilities

| Component | Usage | Risk |
|---|---|---|
| `LiquidityAmounts` | Computing liquidity from token amounts | **Imported from `v4-core/test/utils/`** — test utility, not production library. May not be audited to production standards. |
| `TickMath` | Tick-to-sqrtPrice conversion | Production library, well-audited |

**FINDING:** `LiquidityAmounts` is imported from the test utilities directory (`v4-core/test/utils/LiquidityAmounts.sol`). While the math is likely correct (port of V3's LiquidityAmounts), using test utilities in production contracts is a code smell and may miss edge cases not covered by test-only auditing.

---

## 5. Known Risk Areas

### 5.1 Cross-Contract Reentrancy via PoolManager Callbacks

**Scenario:** During `rebalance() → _addLiquidity() → poolManager.unlock() → unlockCallback() → modifyLiquidity()`, the PoolManager calls the hook's `afterAddLiquidity()` (if the hook has that permission). In this system, `afterAddLiquidity` is a no-op returning the selector, so no direct exploit path exists.

However, the more concerning path:
1. Vault calls `_addLiquidity()` → `poolManager.unlock()`
2. Inside unlock, vault calls `modifyLiquidity()` which changes pool state
3. If someone can trigger another `unlock()` or callback within this context...

**Current Protection:** The vault has `nonReentrant` on `rebalance()`, `deposit()`, and `emergencyWithdraw()`. The `_pendingAction` state variable provides implicit reentrancy protection in the callback. The hook's `onlyPoolManager` modifier prevents external calls.

**Residual Risk:** LOW for direct reentrancy. The hook's afterSwap cannot be triggered during modifyLiquidity (only during swaps). However, if the vault processes positive deltas (takes tokens from pool), the ERC20 transfer could trigger a callback on a malicious token — mitigated by the fact that pool tokens are set by the owner via `setPoolKey`.

### 5.2 Oracle Manipulation (EWMA Can Be Slowly Gamed)

**Attack Vector:**
1. Attacker makes a series of swaps over 20+ blocks, each moving the tick significantly
2. Each swap updates EWMA variance with 6% weight (1 - lambda)
3. After ~11 swaps (half-life), EWMA reflects attacker-controlled variance
4. This can force LP toggle in either direction

**Impact:**
- Force LP ON during high vol → vault suffers IL
- Force LP OFF during low vol → vault misses fee income
- Neither directly steals funds, but degrades vault performance

**Cost to Attacker:** Must pay swap fees + slippage on each manipulation swap. In a low-liquidity pool, this could be cheap. The 24-hour cooldown limits the frequency of exploitation.

**Compounding Keeper Push:**
- Keeper can push vol to 4x current per call
- Over N calls: vol can grow to 4^N * initial (if done before decay)
- With lambda=0.94 and 1-hour implied period, decay is slow enough for multi-call escalation

### 5.3 Keeper Key Compromise Impact

**Capabilities of Compromised Keeper:**
1. `pushVolEstimate()` — push false vol (rate-limited to 4x, except from zero)
2. `triggerEvaluation()` — force LP toggle evaluation (cooldown-gated)
3. `rebalance()` — actually permissionless, anyone can call

**Maximum Damage:**
- Cannot steal funds directly
- Can manipulate vol oracle to force wrong LP decisions
- Can push var to uint128.max if current var is 0 (edge case)
- Impact is degraded strategy performance, not fund theft
- **Mitigation:** Two-step ownership transfer on both Hook and Vault prevents escalation to owner

### 5.4 Price Manipulation During Rebalance

**Critical Gap: `rebalance()` does NOT call `_checkTWAP()`**

**Attack Scenario:**
1. Attacker executes large swap to move pool price (or flash loan)
2. Attacker calls `rebalance()` — now permissionless
3. Vault reads manipulated `sqrtPriceX96` in `_executeAddLiquidity()`
4. `LiquidityAmounts.getLiquidityForAmounts()` computes liquidity based on manipulated price
5. Vault adds liquidity at wrong ratio (too much of one token, not enough of other)
6. Attacker reverses the price manipulation
7. Vault's LP position is now underwater, suffering immediate IL

**Severity:** HIGH. The vault splits assets 50/50 (`amount0 = assets/2, amount1 = assets/2`) regardless of current price. If the price is manipulated, the actual token ratio needed differs from 50/50, meaning one side's contribution is underutilized and the position is immediately impaired.

**Additional Rebalance Concerns:**
- The 50/50 split is only valid when both tokens have the same decimals and price ≈ 1:1. The code comment acknowledges this: "simplified for same-decimal pairs" and "Production: use oracle for cross-token valuation"
- `totalAssets()` sums `lpValue0 + lpValue1` directly, which is only correct for 1:1 priced pairs

### 5.5 Withdrawal Fee Accounting Bug

In `beforeWithdraw()`:
```solidity
uint256 fee = (assets * withdrawalFeeBps) / 10_000;
accumulatedFees += fee;
```

The fee is calculated and added to `accumulatedFees`, but the `assets` amount passed to the actual ERC4626 withdrawal logic is NOT reduced by the fee. The user receives the full `assets` amount. The fee effectively comes from the vault's total assets, diluting all remaining depositors rather than deducting from the withdrawing user.

When `claimFees()` is called, it transfers from the vault's balance — but this amount was never actually retained from the withdrawal. If the vault's idle balance drops below `accumulatedFees`, the owner cannot claim, and the accounting is broken.

### 5.6 LP Range Stale After Removal

When `_executeRemoveLiquidity()` is called, it fetches the current tick range from `hook.getPoolStrategy()`. If the owner has called `setLPRange()` on the hook between add and remove, the removal uses the NEW tick range but the liquidity was deployed at the OLD tick range. This would cause `modifyLiquidity` with a negative delta on a range that has no liquidity, potentially reverting or returning zero.

### 5.7 Missing Slippage Protection

Neither `_executeAddLiquidity()` nor `_executeRemoveLiquidity()` have slippage parameters. The vault accepts whatever amounts the PoolManager returns. Combined with the lack of TWAP checks on rebalance, this amplifies the price manipulation risk.

### 5.8 AlwaysLPVault Control — Phantom Accounting

`AlwaysLPVault.rebalance()` does `deployedAssets += idle` but never actually deploys to a pool. The idle tokens remain in the contract but are counted as "deployed." This means `totalAssets()` double-counts them: `asset.balanceOf(address(this))` already includes them, and `deployedAssets` counts them again. This is a control/benchmark contract so the impact is limited to incorrect performance comparison.

---

## Summary of Findings by Severity

| # | Finding | Severity | Location |
|---|---|---|---|
| 5.4 | Rebalance has no TWAP/price check — LP at manipulated price | HIGH | ILAlphaVault.rebalance() |
| 5.5 | Withdrawal fee not deducted from user — dilutes vault | MEDIUM | ILAlphaVault.beforeWithdraw() |
| 5.6 | LP range change between add/remove causes wrong tick range on removal | MEDIUM | ILAlphaVault + ILAlphaHook.setLPRange() |
| 5.7 | No slippage protection on LP operations | MEDIUM | ILAlphaVault._executeAddLiquidity/Remove |
| 5.2 | EWMA can be gamed over ~11 blocks | MEDIUM | ILAlphaHook._updateVolOracle() |
| 5.3b | Keeper can set unlimited vol when ewmaVar == 0 | MEDIUM | ILAlphaHook.pushVolEstimate() |
| 3.4 | TWAP check uses lastTick not true TWAP — weak protection | MEDIUM | ILAlphaVault._checkTWAP() |
| 4.3 | LiquidityAmounts imported from test utils | LOW | ILAlphaVault import |
| 3.2 | Fee/IL units may not be comparable | LOW | ILAlphaHook._computeFeeAndIL() |
| 5.8 | AlwaysLPVault double-counts assets | LOW | AlwaysLPVault.rebalance() |
| 3.5 | Cooldown bypass via volume spike (by design) | INFO | ILAlphaHook.afterSwap() |
