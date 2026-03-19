# 07 — Differential Security Review

**Date:** 2026-03-20
**Methodology:** Trail of Bits-style differential analysis
**Scope:** All changes across the last 5 significant contract commits (`ad1dfe6` through `10a648f`)
**Contracts Reviewed:** ILAlphaHook.sol, ILAlphaVault.sol, BaseVault.sol, SwapHelper.sol, AlwaysLPVault.sol, HODLVault.sol

---

## 1. Change Analysis

The 5 most recent commits touching `contracts/src/` are:

| Commit | Description | Category |
|--------|-------------|----------|
| `10a648f` | CODE FREEZE v2: public rebalance, UNAUDITED flag | **Access control change** |
| `e811af6` | CODE FREEZE: security hardened, audit-ready | Config/docs |
| `efcfc9f` | Deposit cap, keeper separation, rate limits | **New feature + security hardening** |
| `7bd7183` | Volume spike trigger, emergency LP removal | **New feature** |
| `ad1dfe6` | Real-time LP valuation, TWAP check, withdrawal fee | **Bugfix + new feature** |

### Change Summary

**ILAlphaHook.sol:**
- Added `SPIKE_MULTIPLIER` constant and `VolumeSpikeDetected` event
- Volume spike detection in `afterSwap()` — bypasses cooldown to turn LP off
- Rate-limiting on `pushVolEstimate()` — caps external var at 4x current
- Added `UNAUDITED` constant (bool)

**ILAlphaVault.sol:**
- Added `keeper` address and `onlyKeeper` modifier
- Added `depositCap` with enforcement in `deposit()` and `maxDeposit()` override
- **Removed `onlyKeeper` from `rebalance()`** — now public (anyone can call)
- Added `UNAUDITED` constant (bool)
- Added `setKeeper()`, `setDepositCap()` admin functions

**BaseVault.sol, SwapHelper.sol, AlwaysLPVault.sol, HODLVault.sol:**
- No changes in the reviewed commit range.

---

## 2. Security Regression Check

### 2.1 Access Control Changes

#### FINDING: `rebalance()` changed from `onlyKeeper` to public [MEDIUM-LOW]

**Diff (commit efcfc9f -> 10a648f):**
```
- function rebalance() external onlyKeeper whenNotPaused nonReentrant {
+ function rebalance() external whenNotPaused nonReentrant {
```

**History:** The function was first made `onlyKeeper` in `efcfc9f` ("Security hardening for mainnet"), then the `onlyKeeper` modifier was removed in `10a648f` ("CODE FREEZE v2") one commit later.

**Analysis:** The developer's rationale is documented: "Result is deterministic (hook signal only). Keeper liveness is not a single point of failure." This is architecturally sound because:
- The rebalance outcome is entirely determined by `hook.isLPActive(poolKey)`, which the caller cannot influence.
- Making it public removes a liveness dependency on the keeper.
- `whenNotPaused` and `nonReentrant` guards remain intact.

**Risk:** Low. A griefer could call `rebalance()` to force gas costs on LP add/remove operations, but cannot influence the direction. The only concern is front-running: if a MEV searcher sees the hook toggle and front-runs with a rebalance, the vault still acts on the correct signal. No funds at risk.

**Recommendation:** Acceptable design decision. Consider adding a gas stipend comment for auditors.

#### FINDING: `keeper` address added but `onlyKeeper` modifier unused on vault [INFO]

The `keeper` variable and `onlyKeeper` modifier were added to `ILAlphaVault.sol` in `efcfc9f`, but after `10a648f` removed it from `rebalance()`, the modifier is now **dead code** — no function in the vault uses `onlyKeeper`.

**Risk:** None (dead code, not a vulnerability). But it adds confusion during audit.

**Recommendation:** Either remove the dead `keeper`/`onlyKeeper` from the vault, or document that it is reserved for future use.

### 2.2 Removed Safety Checks

No `require` or `revert` statements were removed. All changes were additive.

### 2.3 New External Call Patterns

No new external call patterns introduced. The existing `poolManager.unlock()` callback pattern is unchanged.

### 2.4 Changed Math/Precision

#### FINDING: `pushVolEstimate` rate limit uses 4x, not 2x as documented [LOW]

**Code (ILAlphaHook.sol:366):**
```solidity
/// @dev Rate limited: max change per push is 2x current value
uint256 maxExternal = currentVar == 0 ? type(uint128).max : currentVar * 4;
```

The NatSpec says "2x current value" but the code caps at `4x`. Since the result is blended 50/50, the maximum new value is `(current + 4*current) / 2 = 2.5 * current`, which is indeed more than 2x but less than 4x.

**Risk:** Low. The rate limit still provides meaningful protection against keeper key compromise. A compromised keeper could ramp vol by ~2.5x per call, requiring multiple sequential calls to reach dangerous levels. However, there is no per-block rate limit, so a compromised keeper could call `pushVolEstimate` multiple times in one transaction to escalate vol exponentially.

**Recommendation:** Add a per-block or per-epoch rate limit. Even a simple `lastPushTimestamp` with a minimum interval (e.g., 1 minute) would prevent single-transaction vol escalation attacks.

#### FINDING: When `ewmaVar == 0`, rate limit allows `type(uint128).max` [LOW]

**Code (ILAlphaHook.sol:366):**
```solidity
uint256 maxExternal = currentVar == 0 ? type(uint128).max : currentVar * 4;
```

When the oracle has zero variance (initial state or after many zero-pushes), the rate limit is effectively disabled. A compromised keeper could push `type(uint128).max` in a single call.

**Risk:** Low, because the blending formula `(0 + uint128.max) / 2` limits the result to half of `uint128.max`, and the pool must still be past cooldown for this to toggle LP. However, it defeats the purpose of rate limiting at initialization.

**Recommendation:** Use a sensible default floor: `maxExternal = currentVar == 0 ? SOME_MAX_INITIAL_VAR : currentVar * 4`.

---

## 3. Blast Radius Assessment

| Change | Blast Radius | Worst Case |
|--------|-------------|------------|
| Public `rebalance()` | Low | Griefer forces unnecessary LP add/remove gas costs; no fund loss |
| Volume spike detection | Medium | False positive spike (e.g., legitimate large trade) disables LP unnecessarily; 24h cooldown locks LP off. Depositors lose yield but not principal |
| Deposit cap | Low | Owner sets cap to 0, blocking deposits. Emergency withdraw still works for existing depositors |
| Keeper rate limit (4x) | Medium | Compromised keeper ramps vol via repeated calls, forces LP off. Mitigated by 50% blending and cooldown, but no per-block limit |
| UNAUDITED constant | None | Informational only, occupies zero additional storage (constant) |

---

## 4. Test Coverage of Recent Changes

### Covered

| Feature | Test | File |
|---------|------|------|
| Deposit cap enforcement | `test_depositCap_enforced` | ILAlphaVault.t.sol:499 |
| Deposit cap `maxDeposit()` | `test_depositCap_maxDeposit` | ILAlphaVault.t.sol:508 |
| Deposit cap only-owner | `test_setDepositCap_onlyOwner` | ILAlphaVault.t.sol:515 |
| Public rebalance | `test_rebalance_publicCallable` | ILAlphaVault.t.sol:523 |
| Keeper set/access (vault) | `test_setKeeper_vault`, `test_setKeeper_vault_onlyOwner` | ILAlphaVault.t.sol:529-539 |
| Withdrawal fee recording | `test_withdrawalFee_recorded` | ILAlphaVault.t.sol:543 |
| Withdrawal fee cap | `test_setWithdrawalFee_maxCap` | ILAlphaVault.t.sol:567 |
| Keeper rate limit | `test_keeper_pushVolEstimate_rateLimited` | ILAlphaHook.t.sol:280 |

### NOT Covered (Gaps)

| Missing Test | Severity | Description |
|--------------|----------|-------------|
| Volume spike detection | **HIGH** | No test for `VolumeSpikeDetected` event, spike bypassing cooldown, or LP toggling off on spike. The entire `SPIKE_MULTIPLIER` feature is untested. |
| Repeated `pushVolEstimate` escalation | **MEDIUM** | No test verifying that a keeper cannot ramp vol to dangerous levels via multiple sequential pushes within one block. |
| Deposit cap edge: exactly at cap | **LOW** | No test for `deposit(exact_remaining_cap)` — only over-cap tested. |
| Withdrawal fee actual deduction | **MEDIUM** | Test only checks `accumulatedFees > 0` but does not verify that the withdrawer received fewer tokens. The fee is accounting-only — `beforeWithdraw` records it but does not reduce `assets` or shares. This is potentially a bug (see Section 5). |
| `claimFees` happy path | **LOW** | Only tests access control, not that fees are actually transferred. |
| `UNAUDITED` constant existence | **INFO** | Not tested, but trivial (constant). |

---

## 5. Critical Bug: Withdrawal Fee is Accounting-Only (Not Enforced)

**Location:** `ILAlphaVault.sol:299-312`

```solidity
function beforeWithdraw(uint256 assets, uint256 /* shares */) internal override {
    _checkTWAP();
    if (withdrawalFeeBps > 0) {
        uint256 fee = (assets * withdrawalFeeBps) / 10_000;
        accumulatedFees += fee;  // <-- Records fee but does NOT reduce assets
    }
    uint256 idle = asset.balanceOf(address(this));
    if (idle < assets && deployedLiquidity > 0) {
        _removeLiquidity();
    }
}
```

The withdrawal fee increments `accumulatedFees` but does not reduce the `assets` parameter or otherwise prevent the full amount from being transferred to the withdrawer. The ERC-4626 `withdraw` function in solmate's `ERC4626.sol` will transfer the full `assets` amount regardless.

**Impact:** HIGH. The fee is a phantom — it is "recorded" but never actually deducted from the withdrawal. When the owner calls `claimFees()`, they will attempt to transfer tokens that may not exist (taken by withdrawers), potentially reverting or stealing from other depositors' assets.

**Recommendation:** Either:
1. Override `withdraw`/`redeem` to reduce the transferred amount by the fee, or
2. Use `previewWithdraw`/`previewRedeem` to inflate the share cost to account for fees, or
3. Remove the fee mechanism until properly implemented.

---

## 6. Dependency Changes

No new imports or library changes in the reviewed commit range. All dependencies (solmate, v4-core) remain unchanged.

The `UNAUDITED` constant uses `bool public constant` which compiles to a pure getter and does not affect storage layout.

---

## 7. Storage Layout Analysis

### ILAlphaVault.sol — New storage variables added in `efcfc9f`:

**Before:**
```
slot 0+: [inherited ERC4626/ERC20 state]
owner          — slot N
pendingOwner   — slot N+1
paused         — slot N+2 (packed with _locked)
_locked        — slot N+2 (packed)
deployedLiquidity — slot N+3
twapThreshold  — slot N+4
withdrawalFeeBps — slot N+5
accumulatedFees — slot N+6
_pendingAction — slot N+7
```

**After (new variables inserted):**
```
owner          — slot N
pendingOwner   — slot N+1
keeper         — slot N+2       ← NEW (inserted between pendingOwner and paused)
paused         — slot N+3       ← SHIFTED
_locked        — slot N+3       ← SHIFTED
deployedLiquidity — slot N+4   ← SHIFTED
depositCap     — slot N+5       ← NEW
twapThreshold  — slot N+6       ← SHIFTED
...
```

**Risk:** This is a **storage layout break**. If this contract were used behind a proxy (UUPS/TransparentProxy), inserting `keeper` and `depositCap` would corrupt all subsequent storage slots. However, the codebase shows no proxy pattern — contracts are deployed directly. Since the contract was redeployed (not upgraded), this is **not a live issue** but should be documented for future reference.

**Recommendation:** If proxy upgrades are ever planned, storage variables must only be appended, never inserted.

---

## 8. Additional Observations

### 8.1 `_checkTWAP` uses hook's `lastTick` as TWAP proxy

The TWAP check at `ILAlphaVault.sol:337-355` compares the current spot tick against `volOracles[poolId].lastTick`, which is updated on every swap. This is NOT a true TWAP — it is the tick from the most recent swap. An attacker who can execute two swaps in sequence (sandwich) can move `lastTick` to match the manipulated spot price, bypassing the check entirely.

This was noted in the code comments ("V4 doesn't have built-in observe() for TWAP, so we use the hook's lastTick as a proxy") but remains a known limitation with real exploit potential.

### 8.2 `SwapHelper.sol` uses raw `transferFrom` instead of `safeTransferFrom`

`SwapHelper.sol:82,89` uses `ERC20(...).transferFrom(...)` without checking the return value. While solmate's `MockERC20` reverts on failure, non-standard tokens (USDT, etc.) may return false silently.

**Risk:** Low for testnet. Must be fixed before mainnet with non-standard tokens.

### 8.3 `AlwaysLPVault.rebalance()` has no access control

`AlwaysLPVault.sol:33` — `rebalance()` is fully public with no `onlyOwner` or `onlyKeeper` modifier. Anyone can trigger it. Since this is a control/benchmark vault, the risk is acceptable, but it should be documented.

---

## 9. Summary of Findings

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Withdrawal fee is accounting-only, never deducted from withdrawal | **HIGH** | Open |
| 2 | Volume spike detection (SPIKE_MULTIPLIER) has zero test coverage | **HIGH** (testing gap) | Open |
| 3 | `_checkTWAP` uses last swap tick, not actual TWAP — bypassable via sandwich | **MEDIUM** | Known limitation |
| 4 | `pushVolEstimate` has no per-block rate limit; repeated calls can escalate vol exponentially | **MEDIUM** | Open |
| 5 | Rate limit documentation says "2x" but code allows 4x external var | **LOW** | Open |
| 6 | `ewmaVar == 0` disables rate limit entirely | **LOW** | Open |
| 7 | Dead `keeper`/`onlyKeeper` code in vault after public rebalance change | **INFO** | Open |
| 8 | Storage layout would break proxy upgrades (no proxy currently used) | **INFO** | Open |
| 9 | `SwapHelper` uses raw `transferFrom` instead of `safeTransferFrom` | **LOW** | Open |

---

*Report generated by Trail of Bits-style differential analysis. All findings should be verified by manual review and on-chain testing before mainnet deployment.*
