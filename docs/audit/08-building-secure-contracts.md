# Trail of Bits "Building Secure Contracts" Assessment

**Project:** IL Alpha Vault
**Date:** 2026-03-20
**Methodology:** Trail of Bits SCV framework + Building Secure Contracts guidelines
**Scope:** `ILAlphaHook.sol`, `ILAlphaVault.sol`, `BaseVault.sol`, `SwapHelper.sol`, `AlwaysLPVault.sol`, `HODLVault.sol`
**Tests reviewed:** `ILAlphaHook.t.sol`, `ILAlphaVault.t.sol`, `ControlVaults.t.sol`

---

## Part A: Code Maturity Scorecard

| # | Category | Score | Notes |
|---|----------|-------|-------|
| 1 | **Arithmetic** | 4/5 | Solidity 0.8.26 provides built-in overflow protection. EWMA calculations use explicit uint128 capping. `FixedPointMathLib.mulDivDown/Up` for share math. Minor concern: `squaredReturn * 3600 / elapsed` can lose precision when elapsed is large; `_computeFeeAndIL` division order could lose precision for small `poolFee * ewmaVolume` products. |
| 2 | **Auditing & Logging** | 4/5 | Comprehensive events: `VolUpdated`, `LPToggled`, `KeeperVolPushed`, `PoolRegistered`, `VolumeSpikeDetected`, `Rebalanced`, `EmergencyWithdraw`, ownership transfer events. Missing: no event on `setKeeper`, `setLambda`, `setLPRange`, `setPoolKey`, `setPaused`, `setDepositCap`, `setTwapThreshold`, `setWithdrawalFeeBps`, or `claimFees`. Admin parameter changes are silent. |
| 3 | **Authentication & Access Control** | 4/5 | Two-step ownership on both Hook and Vault. Keeper role with owner fallback. `onlyPoolManager` guards callbacks. `nonReentrant` on deposit/withdraw/rebalance/emergency. Missing: no zero-address check on `setKeeper`, `transferOwnership`. No multi-sig enforcement. No timelock on critical parameter changes. |
| 4 | **Complexity Management** | 4/5 | Clean separation: `BaseVault` (ERC-4626 + virtual shares), `ILAlphaHook` (oracle + toggle), `ILAlphaVault` (vault + rebalance). Control vaults are minimal. `SwapHelper` is a testnet utility. Inheritance depth is shallow (BaseVault -> ERC4626). DRY via `_computeFeeAndIL`. The `_pendingAction` enum pattern for callback dispatch is clear. |
| 5 | **Decentralization** | 3/5 | Owner can: pause, set deposit cap, change withdrawal fee, change TWAP threshold, set pool key, set LP range, change lambda, emergency withdraw. No timelock or governance. Keeper can push vol estimates (rate-limited to 4x, good). `rebalance()` is public (good -- no keeper liveness dependency). Owner is a single EOA with broad power. |
| 6 | **Documentation** | 3/5 | Good NatSpec on contracts and key functions. Architecture diagram in ILAlphaHook header. Inline comments explain EWMA math and gamma exposure model. Missing: no NatSpec on many admin functions. No formal specification. No architecture docs beyond inline. `UNAUDITED` flag is a responsible disclosure. |
| 7 | **MEV & Frontrunning** | 3/5 | TWAP check (`_checkTWAP`) guards deposits and withdrawals against price manipulation. Withdrawal fee (0.1% default, max 1%) deters sandwich attacks. Volume spike detection (3x EWMA) triggers emergency LP-off. Concerns: TWAP proxy uses hook's `lastTick` (single-sample, not true TWAP -- manipulable within one block if oracle hasn't updated); `rebalance()` is public and could be sandwich-targeted since `_addLiquidity` has no slippage protection. |
| 8 | **Low-level Code** | 5/5 | No assembly, no `delegatecall`, no `selfdestruct`, no `CREATE2` in contract code. All interactions through typed interfaces. `BalanceDelta` unwrapping uses safe cast patterns (`uint256(uint128(-d0))`). Hook address validation done via `Hooks.validateHookPermissions` in constructor. |
| 9 | **Testing** | 4/5 | 50+ tests across 3 test files. Unit tests cover: registration, vol oracle updates, LP toggle lifecycle, cooldown, keeper functions, admin access control, ownership transfer, deposit/withdraw, virtual shares inflation defense, emergency withdraw, deposit cap, rebalance integration, control vaults. Fuzz tests: lambda bounds, LP range validation, pushVol capping, deposit-withdraw round-trip, share monotonicity, multi-depositor fairness. Missing: no invariant tests, no formal verification, no edge-case tests for extreme EWMA values, no cross-contract reentrancy tests. |

**Aggregate Score: 34/45 (76%)**

---

## Part B: Vulnerability Scan (SCV Framework)

### CRITICAL -- None Found

### HIGH Severity

#### H-1: Withdrawal Fee Accounting Bug -- Fee Not Actually Deducted from User

**Location:** `ILAlphaVault.sol:299-311` (`beforeWithdraw`)
**Description:** The `beforeWithdraw` hook increments `accumulatedFees` but never reduces the actual assets transferred to the withdrawer. The fee is recorded in accounting but the user receives the full amount. The `ERC4626.withdraw/redeem` flow in solmate transfers `assets` to the receiver after `beforeWithdraw` runs -- but `assets` was computed *before* `beforeWithdraw`, so the fee is never deducted. This means:
1. `accumulatedFees` grows as a phantom balance with no backing tokens.
2. `claimFees()` will attempt to transfer tokens that don't exist (or steals from other depositors' principal).

**Impact:** Owner calling `claimFees` drains depositor funds. Alternatively, if vault runs out of idle tokens, `claimFees` reverts.
**Recommendation:** Either reduce the assets amount within `beforeWithdraw` (requires overriding `withdraw`/`redeem` to pass adjusted amounts), or implement fee deduction by holding back tokens during the transfer.

#### H-2: No Slippage Protection on Add/Remove Liquidity

**Location:** `ILAlphaVault.sol:224-265, 275-295`
**Description:** `_executeAddLiquidity` and `_executeRemoveLiquidity` call `poolManager.modifyLiquidity` without any minimum output checks. A MEV bot could sandwich the `rebalance()` call: manipulate the pool price before the transaction, causing the vault to add liquidity at a skewed ratio, then reverse the manipulation after.
**Impact:** Value extraction from vault depositors on every rebalance.
**Recommendation:** Add minimum amount parameters or compute expected amounts and revert if deviation exceeds a threshold.

#### H-3: TWAP Oracle is Single-Sample, Not True TWAP

**Location:** `ILAlphaVault.sol:337-355`
**Description:** `_checkTWAP` compares the current spot tick against `volOracles[poolId].lastTick`, which is simply the tick at the time of the last swap that triggered the hook. This is not a time-weighted average price. If the last swap was in the same block (or very recently), `lastTick` closely tracks spot price, making the check useless against flash-loan manipulation. An attacker can: (1) manipulate price, (2) trigger a small swap to update `lastTick`, (3) deposit/withdraw at the manipulated price, all in one transaction.
**Impact:** Flash-loan price manipulation bypasses the TWAP guard.
**Recommendation:** Implement a proper TWAP using observation history (multiple samples over time) or use an external oracle (Chainlink).

### MEDIUM Severity

#### M-1: Keeper Can Manipulate Vol Oracle to Force LP Toggle

**Location:** `ILAlphaHook.sol:359-377`
**Description:** While `pushVolEstimate` is rate-limited to 4x current variance per call, a keeper can make repeated calls. Starting from `ewmaVar = 0` (initial state), the first push can set `ewmaVar` up to `type(uint128).max / 2` (the blend of 0 and uint128.max). Subsequent pushes can maintain artificially high or low variance. The 4x rate limit only applies when `currentVar > 0`, and when `currentVar == 0`, `maxExternal = type(uint128).max`.
**Impact:** Compromised keeper can force LP activation/deactivation at will.
**Recommendation:** Add a cooldown between keeper pushes. Set a reasonable maximum for `maxExternal` when `currentVar == 0` (e.g., a protocol-level max variance cap).

#### M-2: `AlwaysLPVault` Double-Counts Assets

**Location:** `AlwaysLPVault.sol:28-30, 33-39`
**Description:** `totalAssets()` returns `balanceOf(address(this)) + deployedAssets`. But `rebalance()` adds idle to `deployedAssets` without transferring tokens out. After rebalance, tokens are still in the vault AND counted in `deployedAssets`, doubling the apparent total assets. This inflates share prices and breaks ERC-4626 accounting.
**Impact:** Share price inflation in the control vault. Since this is a benchmark vault, it primarily affects performance comparison accuracy rather than user funds in the main vault.
**Recommendation:** Either transfer tokens out during rebalance or track deployment without keeping tokens idle.

#### M-3: Missing Event Emissions on Admin Parameter Changes

**Location:** `ILAlphaHook.sol:390-395, 438-445`, `ILAlphaVault.sol:403-437`
**Description:** `setKeeper`, `setLambda`, `setLPRange`, `setPoolKey`, `setPaused`, `setDepositCap`, `setTwapThreshold`, `setWithdrawalFeeBps` do not emit events. Off-chain monitoring systems cannot detect parameter changes.
**Impact:** Reduces transparency and makes incident response harder. A compromised owner could silently change critical parameters.
**Recommendation:** Add events for every admin state change.

#### M-4: Owner Can Set `twapThreshold` to `type(int24).max`, Disabling TWAP Guard

**Location:** `ILAlphaVault.sol:425-427`
**Description:** `setTwapThreshold` has no bounds check. Owner can set it to an extremely large value, effectively disabling the manipulation protection.
**Impact:** Removes sandwich/flashloan defense if owner is compromised.
**Recommendation:** Add upper bound validation (e.g., max 1000 ticks).

#### M-5: `rebalance()` 50/50 Split Assumption Leaks Value

**Location:** `ILAlphaVault.sol:233-235`
**Description:** `_executeAddLiquidity` splits assets 50/50 between token0 and token1. But: (a) the vault only holds one asset type (the `asset` token), and (b) for non-1:1 price pairs, the optimal ratio depends on the current price and tick range. The comment says "simplified for same-decimal pairs" -- but even with same decimals, price != 1:1 after any swap.
**Impact:** Suboptimal LP deployment; unused tokens left idle; potential revert if vault lacks the counterpart token.
**Recommendation:** Use single-sided deposit with a swap, or compute the correct ratio based on current sqrtPrice and tick range.

### LOW Severity

#### L-1: Missing Zero-Address Checks

**Location:** `ILAlphaHook.sol:438` (`setKeeper`), `ILAlphaHook.sol:426` (`transferOwnership`), `ILAlphaVault.sol:391,417`
**Description:** Setting keeper or pending owner to `address(0)` would lock out keeper functionality or make ownership irrecoverable.
**Recommendation:** Add `require(addr != address(0))`.

#### L-2: `SwapHelper` Uses `transferFrom` Instead of `safeTransferFrom`

**Location:** `SwapHelper.sol:82, 89, 117, 124`
**Description:** `ERC20.transferFrom` is used directly. Non-standard ERC20 tokens (e.g., USDT) that don't return `bool` will cause silent failures.
**Impact:** Low -- `SwapHelper` is a testnet utility, not production code.
**Recommendation:** Use `SafeTransferLib.safeTransferFrom`.

#### L-3: `beforeWithdraw` Calls `_removeLiquidity` Inside Solmate's `withdraw` Flow

**Location:** `ILAlphaVault.sol:299-312`
**Description:** `_removeLiquidity` triggers `poolManager.unlock` which is an external call. This happens inside `beforeWithdraw`, which is called within ERC4626's `withdraw`/`redeem`. While `nonReentrant` on `deposit` prevents re-entry, the unlock callback pattern within a withdrawal flow is a complex control flow that could interact unexpectedly with future code changes.
**Recommendation:** Document this interaction pattern clearly. Consider separating LP removal from the withdrawal flow (require explicit `rebalance()` before withdraw).

#### L-4: Cooldown Bypass via Volume Spike

**Location:** `ILAlphaHook.sol:250-255`
**Description:** Volume spike detection bypasses the 24-hour cooldown and forces LP off. An attacker could craft a large swap specifically to trigger the spike threshold and force an LP-off state. This is by design but creates a griefing vector.
**Recommendation:** Document this as expected behavior. Consider requiring multiple consecutive spikes before emergency toggle.

#### L-5: `setPoolKey` Can Be Called Multiple Times

**Location:** `ILAlphaVault.sol:403-411`
**Description:** Owner can change the pool key at any time, even when liquidity is deployed. If changed while `deployedLiquidity > 0`, the vault loses track of its position in the old pool and the `_executeRemoveLiquidity` call would attempt to remove from the new (wrong) pool.
**Impact:** Stranded liquidity in the old pool.
**Recommendation:** Require `deployedLiquidity == 0` before allowing pool key change.

### INFORMATIONAL

| ID | Finding | Location |
|----|---------|----------|
| I-1 | `UNAUDITED` constant is a responsible transparency measure | Both contracts |
| I-2 | `receive() external payable {}` in tests -- acceptable for test contracts | Test files |
| I-3 | Solmate ERC4626 used as base -- well-audited dependency | BaseVault.sol |
| I-4 | `deployCodeTo` in tests is Foundry-specific; deployment scripts should use different approach | Test files |
| I-5 | `annualizedVol` calculation (`hourlyVar * 8760`) is a rough approximation; proper annualization would use `sqrt(hourlyVar) * sqrt(8760)` | ILAlphaHook.sol:402 |

---

### SCV Classes Not Applicable / Not Found

| Vulnerability Class | Status |
|---------------------|--------|
| Reentrancy (classic) | Mitigated -- `nonReentrant` on all external entry points |
| Reentrancy (cross-function) | Mitigated -- `_locked` flag covers deposit/withdraw/rebalance/emergency |
| Reentrancy (read-only) | Low risk -- `totalAssets()` view reads pool state but is called within guarded functions |
| Oracle manipulation (Chainlink) | N/A -- no Chainlink used |
| Flash loan attacks | Partially mitigated (see H-3: TWAP guard is weak) |
| Integer overflow/underflow | Mitigated -- Solidity 0.8.26 + uint128 capping |
| Storage collision | N/A -- no proxy/upgradeable pattern |
| Uninitialized storage | N/A -- all storage initialized in constructors |
| Delegate call injection | N/A -- no delegatecall used |
| Signature replay | N/A -- no signature-based auth |
| ERC-4626 inflation attack | Mitigated -- virtual shares/assets (1e6 offset) |
| Token approval race condition | N/A -- no approve patterns in core contracts |
| Unchecked return values | Mitigated -- SafeTransferLib used in vault (not in SwapHelper) |
| Gas griefing | Low risk -- `rebalance()` is public but deterministic |
| Denial of service | Low risk -- cooldown prevents rapid toggling |

---

## Part C: Guidelines Compliance

| Guideline | Status | Notes |
|-----------|--------|-------|
| Checks-Effects-Interactions | PARTIAL | `beforeWithdraw` performs external calls (`_removeLiquidity` -> `poolManager.unlock`) before state is fully updated in the ERC4626 flow. The `_pendingAction` pattern mitigates risk but violates the strict CEI pattern. |
| SafeTransferLib consistently | PARTIAL | Used in `ILAlphaVault` (`safeTransfer`). Not used in `SwapHelper` (uses raw `transferFrom`). |
| Custom errors | PASS | All contracts use custom errors (`OnlyOwner`, `Paused`, `DepositTooSmall`, etc.). One exception: `setWithdrawalFeeBps` uses `require("Max 1%")` string instead of custom error. |
| Two-step ownership | PASS | Implemented in both `ILAlphaHook` and `ILAlphaVault`. |
| Emergency pause | PASS | `emergencyWithdraw` pulls LP and pauses. Deposits blocked when paused. Withdrawals still allowed (good -- users can exit). |
| Deposit caps | PASS | `depositCap` enforced in `deposit()`. `maxDeposit()` returns remaining capacity. |
| Rate limiting | PARTIAL | Keeper vol pushes rate-limited to 4x. LP toggle has 24h cooldown. No rate limiting on deposits/withdrawals themselves. |
| Event emission for state changes | FAIL | Multiple admin functions lack events (see M-3). |

---

## Part D: Overall Risk Assessment

### Risk Rating: **MEDIUM-HIGH**

The codebase demonstrates strong fundamentals (virtual shares, reentrancy guards, two-step ownership, custom errors, emergency mechanisms) but has several issues that would need resolution before mainnet deployment.

### Top 5 Findings by Severity

| Rank | ID | Severity | Finding | Exploitable? |
|------|-----|----------|---------|-------------|
| 1 | H-1 | HIGH | Withdrawal fee accounting bug -- fees are phantom, `claimFees` drains depositor funds | Yes -- owner calls `claimFees` |
| 2 | H-2 | HIGH | No slippage protection on add/remove liquidity enables MEV sandwich | Yes -- every rebalance |
| 3 | H-3 | HIGH | Single-sample TWAP proxy is bypassable via same-block manipulation | Yes -- via flash loan |
| 4 | M-1 | MEDIUM | Keeper can manipulate vol oracle from zero to max in one call | Yes -- compromised keeper |
| 5 | M-5 | MEDIUM | 50/50 asset split assumption leaks value and may revert | Yes -- at any non-1:1 price |

### Remediation Priority

1. **Immediate (before any deployment):** Fix H-1 (withdrawal fee bug), H-2 (slippage protection), H-3 (proper TWAP or oracle)
2. **Before mainnet:** Fix M-1 (keeper rate limit from zero), M-5 (LP ratio calculation), L-5 (pool key guard)
3. **Before audit:** Add events for all admin changes (M-3), add zero-address checks (L-1), bounds-check `twapThreshold` (M-4)
4. **Recommended:** Add invariant tests, formal verification of share accounting, consider timelock for admin functions

### Audit Readiness Score: **58/100**

| Category | Score | Weight | Rationale |
|----------|-------|--------|-----------|
| Code quality | 8/10 | 20% | Clean, modular, well-structured |
| Security controls | 6/10 | 25% | Good patterns but critical gaps (H-1, H-2, H-3) |
| Test coverage | 7/10 | 20% | Good unit + fuzz tests, missing invariant tests |
| Documentation | 5/10 | 10% | Inline docs good, formal spec missing |
| Access control | 7/10 | 15% | Two-step ownership, but no timelock/multisig |
| MEV resistance | 4/10 | 10% | TWAP check exists but is ineffective |

**Summary:** The codebase is well-architected for an early-stage DeFi protocol. The virtual shares defense, reentrancy guards, emergency pause, and keeper rate-limiting show security awareness. However, three high-severity findings (phantom withdrawal fees, missing slippage protection, weak TWAP oracle) must be resolved before any deployment with real funds. The control vaults have accounting bugs but are lower priority since they serve as benchmarks only. A professional audit should be engaged after remediating the top 5 findings.
