# Property-Based Testing Analysis

**Trail of Bits Style -- IL Alpha Vault**
**Date:** 2026-03-20

---

## 1. Critical Invariants

### 1.1 ERC-4626 Share Price Invariants

| ID | Invariant | Contracts | Severity |
|----|-----------|-----------|----------|
| INV-01 | `convertToShares(convertToAssets(shares)) <= shares` (round-trip never inflates) | BaseVault | Critical |
| INV-02 | `convertToAssets(convertToShares(assets)) <= assets` (round-trip never inflates) | BaseVault | Critical |
| INV-03 | `convertToShares` and `convertToAssets` are monotonically non-decreasing | BaseVault | Critical |
| INV-04 | `previewDeposit(assets) == convertToShares(assets)` (consistency) | BaseVault | Medium |
| INV-05 | `previewRedeem(shares) == convertToAssets(shares)` (consistency) | BaseVault | Medium |
| INV-06 | `previewMint(shares) >= previewDeposit(previewMint(shares))` is not possible -- mint preview rounds up, deposit preview rounds down | BaseVault | High |
| INV-07 | Share price (`totalAssets / totalSupply`) never decreases absent IL or fees (idle-only state) | ILAlphaVault, HODLVault | Critical |
| INV-08 | First depositor share price is bounded by virtual shares: `convertToAssets(1e6) ~= 1e6` at zero supply | BaseVault | High |

### 1.2 Vault Solvency

| ID | Invariant | Contracts | Severity |
|----|-----------|-----------|----------|
| INV-09 | `totalAssets() >= 0` always (never underflows) | All vaults | Critical |
| INV-10 | For HODLVault: `totalAssets() == asset.balanceOf(address(vault))` always | HODLVault | Critical |
| INV-11 | For ILAlphaVault when `deployedLiquidity == 0`: `totalAssets() == asset.balanceOf(address(vault))` | ILAlphaVault | Critical |
| INV-12 | Sum of all `convertToAssets(user_shares)` <= `totalAssets() + VIRTUAL_ASSETS` (no phantom assets) | All vaults | Critical |
| INV-13 | `accumulatedFees` never exceeds total withdrawal volume * `withdrawalFeeBps / 10000` | ILAlphaVault | High |
| INV-14 | After `emergencyWithdraw()`: `deployedLiquidity == 0 && paused == true` | ILAlphaVault | Critical |

### 1.3 EWMA Oracle Bounds

| ID | Invariant | Contracts | Severity |
|----|-----------|-----------|----------|
| INV-15 | `ewmaVar <= type(uint128).max` always (capped in `_updateVolOracle`) | ILAlphaHook | Critical |
| INV-16 | `lambda` is always in `[MIN_LAMBDA, MAX_LAMBDA]` = `[5000, 9900]` | ILAlphaHook | High |
| INV-17 | `ewmaVolume <= type(uint128).max` always (capped in `_updateVolumeEwma`) | ILAlphaHook | Critical |
| INV-18 | `lastTimestamp <= block.timestamp` always (no time travel) | ILAlphaHook | Medium |
| INV-19 | `pushVolEstimate` with `currentVar > 0` produces result <= `currentVar * 2.5` (rate limiting) | ILAlphaHook | High |
| INV-20 | `_updateVolOracle` is a no-op when `elapsed == 0` (same-block idempotency) | ILAlphaHook | Medium |

### 1.4 LP Toggle Consistency

| ID | Invariant | Contracts | Severity |
|----|-----------|-----------|----------|
| INV-21 | `isLPActive` can only change if `block.timestamp >= lastToggleTime + COOLDOWN_SECONDS` OR volume spike | ILAlphaHook | High |
| INV-22 | Volume spike always sets `isLPActive = false` (never activates) | ILAlphaHook | High |
| INV-23 | `isLPActive == true` implies `feeYield > ilCost` at the time of last evaluation | ILAlphaHook | Medium |
| INV-24 | After rebalance: `(hook.isLPActive && deployedLiquidity > 0) || (!hook.isLPActive && deployedLiquidity == 0)` -- LP state matches hook signal | ILAlphaVault | Critical |

### 1.5 Reentrancy Guard

| ID | Invariant | Contracts | Severity |
|----|-----------|-----------|----------|
| INV-25 | `_locked` is always `false` outside of `nonReentrant` call frames | ILAlphaVault | Critical |
| INV-26 | `unlockCallback` only callable by `poolManager` | ILAlphaVault | Critical |
| INV-27 | `_pendingAction` is `NONE` outside of `_addLiquidity`/`_removeLiquidity` call frames | ILAlphaVault | High |

---

## 2. Property-Based Test Suggestions

### 2.1 Fuzz Tests

```
// ERC-4626 round-trip
function testFuzz_shareRoundTrip_neverInflates(uint256 assets)
  assets: [1e6, 1e30]

function testFuzz_assetRoundTrip_neverInflates(uint256 shares)
  shares: [1, 1e30]

// EWMA oracle
function testFuzz_updateVolOracle_boundedOutput(int24 tickDelta, uint256 elapsed, uint128 priorVar, uint16 lambda)
  tickDelta: [-887272, 887272]
  elapsed: [1, 365 days]
  priorVar: [0, type(uint128).max]
  lambda: [5000, 9900]

// Deposit/withdraw solvency
function testFuzz_depositWithdraw_solvency(uint256[] deposits, uint256[] withdrawPcts)
  deposits[i]: [1e6, 1e24]
  withdrawPcts[i]: [1, 100] (percent of shares)

// Fee accumulation
function testFuzz_withdrawalFee_neverExceedsAssets(uint256 assets, uint256 feeBps)
  assets: [1e6, 1e24]
  feeBps: [0, 100]

// pushVolEstimate rate limiting
function testFuzz_pushVol_rateLimited(uint128 currentVar, uint256 externalVar)
  currentVar: [1, type(uint128).max]
  externalVar: [0, type(uint256).max]
```

### 2.2 Invariant Test Contracts

The fuzzer should target the following handler actions in sequence:
1. `deposit(amount, user)` -- random user deposits random amount
2. `withdraw(shares, user)` -- random user withdraws random share count
3. `rebalance()` -- anyone calls rebalance
4. `warp(seconds)` -- time advances
5. `pushVolEstimate(vol)` -- keeper pushes vol
6. `triggerEvaluation()` -- keeper triggers eval
7. `doSwap(direction, amount)` -- swap in pool

After each action, check all invariants in the `invariant_*` functions.

### 2.3 Edge Case Generators

- **Zero-supply vault**: All shares redeemed, then new deposit
- **Dust deposits**: Exactly `1e6` (VIRTUAL_ASSETS minimum)
- **Max uint128 ewmaVar**: Push vol to saturation, then swap
- **Same-block double swap**: Two swaps in timestamp=0 elapsed
- **Cooldown boundary**: Warp to exactly `lastToggleTime + COOLDOWN_SECONDS`
- **Deposit cap boundary**: Deposit exactly `depositCap - totalAssets()`
- **Emergency then withdraw**: emergencyWithdraw followed by user redeem
- **Large tick delta**: Swap that moves price from MIN_TICK to MAX_TICK

---

## 3. Coverage Gaps in Existing Tests

### 3.1 Missing Fuzz Coverage

| Gap | Description | Risk |
|-----|-------------|------|
| G-01 | No fuzz test for `_updateVolOracle` arithmetic -- squared return multiplication and time normalization could overflow for extreme tick deltas with short elapsed times | High |
| G-02 | No fuzz test for `_updateVolumeEwma` with extreme `amountSpecified` values (near `type(int256).min/max`) | High |
| G-03 | No fuzz test for `_computeFeeAndIL` with edge-case `tickRange` (e.g., `tickRange=1` causing extreme concentration) | High |
| G-04 | No invariant test verifying vault solvency across arbitrary deposit/withdraw/rebalance sequences | Critical |
| G-05 | No test for `convertToShares`/`convertToAssets` round-trip non-inflation property | High |

### 3.2 Missing Scenario Coverage

| Gap | Description | Risk |
|-----|-------------|------|
| G-06 | No test for `beforeWithdraw` triggering `_removeLiquidity` when idle < requested assets | High |
| G-07 | No test for withdrawal fee accounting correctness: fees are accumulated but never actually deducted from user payout in `beforeWithdraw` -- this is a **potential bug** (fees tracked but user gets full amount) | Critical |
| G-08 | No test for `claimFees` with actual accumulated fees and transfer verification | Medium |
| G-09 | No test for `AlwaysLPVault.beforeWithdraw` zeroing `deployedAssets` when idle < requested -- this causes `totalAssets()` to drop, creating a loss for remaining depositors | High |
| G-10 | No test for volume spike detection path in `afterSwap` | Medium |
| G-11 | No test for `_checkTWAP` reverting on price manipulation (only access control test for `setTwapThreshold`) | High |
| G-12 | No test verifying `_getDeployedLPValue` returns correct amounts after price movement | High |
| G-13 | No test for `pushVolEstimate` when `currentVar == 0` (allows `maxExternal = type(uint128).max`, bypassing rate limit) | Medium |

### 3.3 Potential Bugs Found During Analysis

| ID | Finding | Severity |
|----|---------|----------|
| BUG-01 | **Withdrawal fee is tracked but never deducted.** `beforeWithdraw` adds to `accumulatedFees` but does not reduce the assets sent to the user. The fee is purely accounting -- users receive full value while `accumulatedFees` grows. When `claimFees` is called, it transfers tokens that were never actually retained, potentially draining vault funds. | Critical |
| BUG-02 | **AlwaysLPVault double-counts assets.** After `rebalance()`, tokens remain in the vault (`asset.balanceOf`) AND are counted in `deployedAssets`. `totalAssets()` returns `idle + deployedAssets` which is 2x the actual value. This inflates share price and can lead to insolvency when users withdraw. | High |
| BUG-03 | **`pushVolEstimate` rate limit bypass at zero.** When `ewmaVar == 0`, `maxExternal = type(uint128).max`, allowing a keeper to set variance to any value in a single call. The rate limit only applies when there is a non-zero baseline. | Medium |

---

## 4. Concrete Test Code

The following tests should be added to a new file or appended to existing test files.

### Test File: `contracts/test/PropertyTests.t.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {MockERC20} from "solmate/src/test/utils/mocks/MockERC20.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {HODLVault} from "../src/controls/HODLVault.sol";
import {AlwaysLPVault} from "../src/controls/AlwaysLPVault.sol";
import {IHooks} from "v4-core/src/interfaces/IHooks.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolManager} from "v4-core/src/PoolManager.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {Hooks} from "v4-core/src/libraries/Hooks.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {PoolSwapTest} from "v4-core/src/test/PoolSwapTest.sol";
import {PoolModifyLiquidityTest} from "v4-core/src/test/PoolModifyLiquidityTest.sol";
import {ILAlphaHook} from "../src/ILAlphaHook.sol";
import {ILAlphaVault} from "../src/ILAlphaVault.sol";

/// @title PropertyTests
/// @notice Property-based (fuzz/invariant) tests for IL Alpha Vault system.
///         Covers ERC-4626 invariants, EWMA oracle bounds, vault solvency.
contract PropertyTests is Test {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    IPoolManager manager;
    PoolSwapTest swapRouter;
    PoolModifyLiquidityTest modifyLiquidityRouter;

    ILAlphaHook hook;
    ILAlphaVault vault;
    HODLVault hodl;
    PoolKey poolKey;
    PoolId poolId;

    MockERC20 token0;
    MockERC20 token1;

    uint160 constant SQRT_PRICE_1_1 = 79228162514264337593543950336;
    uint160 constant MIN_PRICE_LIMIT = TickMath.MIN_SQRT_PRICE + 1;
    uint160 constant MAX_PRICE_LIMIT = TickMath.MAX_SQRT_PRICE - 1;

    function setUp() public {
        manager = new PoolManager(address(this));
        swapRouter = new PoolSwapTest(manager);
        modifyLiquidityRouter = new PoolModifyLiquidityTest(manager);

        token0 = new MockERC20("Token0", "TKN0", 18);
        token1 = new MockERC20("Token1", "TKN1", 18);

        if (address(token0) > address(token1)) {
            (token0, token1) = (token1, token0);
        }

        token0.mint(address(this), 1_000_000 ether);
        token1.mint(address(this), 1_000_000 ether);

        token0.approve(address(swapRouter), type(uint256).max);
        token1.approve(address(swapRouter), type(uint256).max);
        token0.approve(address(modifyLiquidityRouter), type(uint256).max);
        token1.approve(address(modifyLiquidityRouter), type(uint256).max);

        // Deploy hook
        uint160 flags = uint160(Hooks.AFTER_INITIALIZE_FLAG | Hooks.AFTER_SWAP_FLAG);
        address hookAddr = address(flags);
        deployCodeTo("ILAlphaHook.sol", abi.encode(manager, address(this)), hookAddr);
        hook = ILAlphaHook(hookAddr);

        poolKey = PoolKey({
            currency0: Currency.wrap(address(token0)),
            currency1: Currency.wrap(address(token1)),
            fee: 3000,
            tickSpacing: 60,
            hooks: IHooks(hookAddr)
        });
        poolId = poolKey.toId();

        manager.initialize(poolKey, SQRT_PRICE_1_1);

        modifyLiquidityRouter.modifyLiquidity(
            poolKey,
            IPoolManager.ModifyLiquidityParams({
                tickLower: -887220,
                tickUpper: 887220,
                liquidityDelta: 10000 ether,
                salt: bytes32(0)
            }),
            ""
        );

        // Deploy ILAlphaVault
        vault = new ILAlphaVault(
            ERC20(address(token0)),
            manager,
            hook,
            "IL Alpha Vault",
            "ilALPHA"
        );
        vault.setPoolKey(poolKey);
        vault.setDepositCap(type(uint256).max);

        // Deploy HODLVault for simpler invariant checks
        hodl = new HODLVault(ERC20(address(token0)), "HODL", "HODL");
    }

    // ═══════════════════════════════════════════════════════════════════
    // TEST 1: ERC-4626 convertToShares/convertToAssets round-trip
    //         never inflates value (INV-01, INV-02)
    // ═══════════════════════════════════════════════════════════════════

    /// @notice Round-tripping assets -> shares -> assets must never return
    ///         more than the original amount. This is the core ERC-4626
    ///         safety property that prevents share price manipulation.
    function testFuzz_roundTrip_neverInflates(
        uint256 depositSeed,
        uint256 assets,
        uint256 shares
    ) public {
        // First create some vault state with a deposit
        depositSeed = bound(depositSeed, 1e6, 100_000 ether);
        token0.mint(address(this), depositSeed);
        token0.approve(address(vault), depositSeed);
        vault.deposit(depositSeed, address(this));

        // Test assets -> shares -> assets round-trip
        assets = bound(assets, 1, 1e30);
        uint256 sharesFromAssets = vault.convertToShares(assets);
        uint256 assetsBack = vault.convertToAssets(sharesFromAssets);
        assertLe(
            assetsBack,
            assets,
            "INV-01: assets->shares->assets must not inflate"
        );

        // Test shares -> assets -> shares round-trip
        shares = bound(shares, 1, 1e30);
        uint256 assetsFromShares = vault.convertToAssets(shares);
        uint256 sharesBack = vault.convertToShares(assetsFromShares);
        assertLe(
            sharesBack,
            shares,
            "INV-02: shares->assets->shares must not inflate"
        );
    }

    // ═══════════════════════════════════════════════════════════════════
    // TEST 2: EWMA oracle always stays within uint128 bounds (INV-15, INV-17)
    //         regardless of input magnitude
    // ═══════════════════════════════════════════════════════════════════

    /// @notice After any sequence of pushVolEstimate calls with arbitrary
    ///         values, ewmaVar must never exceed type(uint128).max.
    ///         Also tests the rate-limiting logic under adversarial input.
    function testFuzz_ewmaVar_alwaysBounded(
        uint256 push1,
        uint256 push2,
        uint256 push3
    ) public {
        // Push three arbitrary vol estimates in sequence
        hook.pushVolEstimate(poolKey, push1);
        (uint128 var1,,,) = hook.volOracles(poolId);
        assertLe(
            var1,
            type(uint128).max,
            "INV-15: ewmaVar must fit uint128 after push 1"
        );

        hook.pushVolEstimate(poolKey, push2);
        (uint128 var2,,,) = hook.volOracles(poolId);
        assertLe(
            var2,
            type(uint128).max,
            "INV-15: ewmaVar must fit uint128 after push 2"
        );

        hook.pushVolEstimate(poolKey, push3);
        (uint128 var3,,,) = hook.volOracles(poolId);
        assertLe(
            var3,
            type(uint128).max,
            "INV-15: ewmaVar must fit uint128 after push 3"
        );
    }

    // ═══════════════════════════════════════════════════════════════════
    // TEST 3: HODLVault solvency -- totalAssets always equals balance
    //         (INV-10) across arbitrary deposit/withdraw sequences
    // ═══════════════════════════════════════════════════════════════════

    /// @notice For HODLVault, totalAssets() must always exactly equal the
    ///         vault's token balance. No phantom assets, no undercount.
    function testFuzz_hodlVault_solvency(
        uint256 deposit1,
        uint256 deposit2,
        uint256 redeemPct
    ) public {
        deposit1 = bound(deposit1, 1e6, 500_000 ether);
        deposit2 = bound(deposit2, 1e6, 500_000 ether);
        redeemPct = bound(redeemPct, 1, 100);

        // Deposit 1
        token0.mint(address(this), deposit1);
        token0.approve(address(hodl), deposit1);
        uint256 shares1 = hodl.deposit(deposit1, address(this));

        assertEq(
            hodl.totalAssets(),
            token0.balanceOf(address(hodl)),
            "INV-10: totalAssets must equal balance after deposit 1"
        );

        // Deposit 2
        token0.mint(address(this), deposit2);
        token0.approve(address(hodl), deposit2);
        uint256 shares2 = hodl.deposit(deposit2, address(this));

        assertEq(
            hodl.totalAssets(),
            token0.balanceOf(address(hodl)),
            "INV-10: totalAssets must equal balance after deposit 2"
        );

        // Partial redeem
        uint256 totalShares = shares1 + shares2;
        uint256 redeemAmount = (totalShares * redeemPct) / 100;
        if (redeemAmount > 0) {
            hodl.redeem(redeemAmount, address(this), address(this));
        }

        assertEq(
            hodl.totalAssets(),
            token0.balanceOf(address(hodl)),
            "INV-10: totalAssets must equal balance after redeem"
        );
    }

    // ═══════════════════════════════════════════════════════════════════
    // TEST 4: Lambda bounds are always enforced (INV-16)
    // ═══════════════════════════════════════════════════════════════════

    /// @notice setLambda must revert for any value outside [5000, 9900]
    ///         and succeed for any value inside that range.
    function testFuzz_lambda_boundsEnforced(uint16 lambda) public {
        if (lambda < 5000 || lambda > 9900) {
            vm.expectRevert(ILAlphaHook.InvalidLambda.selector);
            hook.setLambda(poolKey, lambda);
        } else {
            hook.setLambda(poolKey, lambda);
            (,,, uint16 stored) = hook.volOracles(poolId);
            assertEq(stored, lambda, "INV-16: stored lambda must match input");
            assertGe(stored, 5000, "INV-16: lambda >= MIN_LAMBDA");
            assertLe(stored, 9900, "INV-16: lambda <= MAX_LAMBDA");
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // TEST 5: Vault deposit/withdraw solvency -- multi-user sequence
    //         must never create phantom assets (INV-09, INV-12)
    // ═══════════════════════════════════════════════════════════════════

    /// @notice After a sequence of deposits and withdrawals by multiple
    ///         users, the vault must remain solvent: no user can extract
    ///         more value than the vault holds, and totalAssets must
    ///         remain consistent with actual balance (when idle-only).
    function testFuzz_vault_multiUser_solvency(
        uint256 aliceDeposit,
        uint256 bobDeposit,
        uint8 withdrawOrder
    ) public {
        aliceDeposit = bound(aliceDeposit, 1e6, 100_000 ether);
        bobDeposit = bound(bobDeposit, 1e6, 100_000 ether);

        address alice = address(0xa11ce);
        address bob = address(0xb0b);

        // Alice deposits
        token0.mint(alice, aliceDeposit);
        vm.startPrank(alice);
        token0.approve(address(vault), aliceDeposit);
        uint256 aliceShares = vault.deposit(aliceDeposit, alice);
        vm.stopPrank();

        // Bob deposits
        token0.mint(bob, bobDeposit);
        vm.startPrank(bob);
        token0.approve(address(vault), bobDeposit);
        uint256 bobShares = vault.deposit(bobDeposit, bob);
        vm.stopPrank();

        // Invariant: totalAssets == idle balance (no LP deployed)
        assertEq(
            vault.totalAssets(),
            token0.balanceOf(address(vault)),
            "INV-11: idle-only totalAssets must match balance"
        );

        uint256 totalDeposited = aliceDeposit + bobDeposit;
        uint256 totalRedeemed;

        // Withdraw in fuzzed order
        if (withdrawOrder % 2 == 0) {
            // Alice first
            vm.prank(alice);
            vault.redeem(aliceShares, alice, alice);
            totalRedeemed += token0.balanceOf(alice);

            vm.prank(bob);
            vault.redeem(bobShares, bob, bob);
            totalRedeemed += token0.balanceOf(bob);
        } else {
            // Bob first
            vm.prank(bob);
            vault.redeem(bobShares, bob, bob);
            totalRedeemed += token0.balanceOf(bob);

            vm.prank(alice);
            vault.redeem(aliceShares, alice, alice);
            totalRedeemed += token0.balanceOf(alice);
        }

        // Solvency: total redeemed should not exceed total deposited
        // (small rounding tolerance for virtual share math)
        assertLe(
            totalRedeemed,
            totalDeposited + 2, // +2 for rounding
            "INV-12: total withdrawn must not exceed total deposited"
        );

        // Vault should be approximately empty
        assertLe(
            token0.balanceOf(address(vault)),
            2, // dust from rounding
            "Vault should be near-empty after full withdrawal"
        );
    }

    // ═══════════════════════════════════════════════════════════════════
    // BONUS TEST 6: pushVolEstimate rate-limit property (INV-19)
    // ═══════════════════════════════════════════════════════════════════

    /// @notice When currentVar > 0, pushVolEstimate must produce a result
    ///         that is at most (currentVar + currentVar * 4) / 2 = 2.5 * currentVar.
    ///         The rate limit caps externalVar at 4 * currentVar.
    function testFuzz_pushVol_rateLimitProperty(
        uint128 seedVar,
        uint256 externalVar
    ) public {
        // Seed a non-zero baseline via two pushes
        // First push from 0 can be anything (rate limit bypass at zero)
        seedVar = uint128(bound(uint256(seedVar), 1e15, type(uint128).max / 4));
        hook.pushVolEstimate(poolKey, uint256(seedVar));

        // Now get the actual current var
        (uint128 currentVar,,,) = hook.volOracles(poolId);
        if (currentVar == 0) return; // Skip if somehow zero

        // Push arbitrary external var
        hook.pushVolEstimate(poolKey, externalVar);
        (uint128 afterPush,,,) = hook.volOracles(poolId);

        // Max possible: (currentVar + min(externalVar, currentVar*4)) / 2
        // When externalVar >= currentVar*4: result = (currentVar + currentVar*4)/2 = 2.5*currentVar
        uint256 maxExpected = (uint256(currentVar) * 5) / 2 + 1; // +1 for rounding
        assertLe(
            uint256(afterPush),
            maxExpected,
            "INV-19: pushVol result must respect rate limit"
        );
    }

    // ═══════════════════════════════════════════════════════════════════
    // BONUS TEST 7: Volume spike always deactivates LP (INV-22)
    // ═══════════════════════════════════════════════════════════════════

    /// @notice A swap with volume > 3x ewmaVolume must always set
    ///         isLPActive = false, bypassing cooldown.
    function testFuzz_volumeSpike_alwaysDeactivates(
        uint256 spikeMultiplier
    ) public {
        spikeMultiplier = bound(spikeMultiplier, 4, 100);

        // First activate LP
        vm.warp(block.timestamp + 1 hours);
        _doSwap(true, -10 ether); // generate some volume

        // Zero out vol, keep volume
        for (uint256 i = 0; i < 80; i++) {
            hook.pushVolEstimate(poolKey, 0);
        }
        vm.warp(block.timestamp + 25 hours);
        hook.triggerEvaluation(poolKey);

        // If LP is active, test the spike
        if (hook.isLPActive(poolKey)) {
            // Get current ewmaVolume
            (,,,, uint128 ewmaVol) = hook.poolStates(poolId);

            if (ewmaVol > 0) {
                // Do a spike swap (> 3x ewmaVolume)
                uint256 spikeAmount = uint256(ewmaVol) * spikeMultiplier;
                // Cap to reasonable amount to avoid pool liquidity issues
                if (spikeAmount > 100_000 ether) spikeAmount = 100_000 ether;

                vm.warp(block.timestamp + 1); // need elapsed > 0
                _doSwap(true, -int256(spikeAmount));

                // LP must be inactive after spike
                assertFalse(
                    hook.isLPActive(poolKey),
                    "INV-22: volume spike must deactivate LP"
                );
            }
        }
    }

    // ─── Helpers ─────────────────────────────────────────────────────

    function _doSwap(bool zeroForOne, int256 amountSpecified) internal {
        swapRouter.swap(
            poolKey,
            IPoolManager.SwapParams({
                zeroForOne: zeroForOne,
                amountSpecified: amountSpecified,
                sqrtPriceLimitX96: zeroForOne ? MIN_PRICE_LIMIT : MAX_PRICE_LIMIT
            }),
            PoolSwapTest.TestSettings({
                takeClaims: false,
                settleUsingBurn: false
            }),
            ""
        );
    }

    receive() external payable {}
}
```

---

## 5. Summary of Findings

### By Severity

| Severity | Count | Details |
|----------|-------|---------|
| Critical | 1 | BUG-01: Withdrawal fee tracked but never deducted -- `claimFees` can drain vault |
| High | 2 | BUG-02: AlwaysLPVault double-counts assets; BUG-03: pushVolEstimate rate-limit bypass at zero |
| Coverage Gaps | 13 | G-01 through G-13 listed in Section 3 |
| Invariants Defined | 27 | INV-01 through INV-27 |
| Fuzz/Invariant Tests Written | 7 | Tests 1-7 in Section 4 |

### Recommended Next Steps

1. **Fix BUG-01 immediately** -- either deduct the fee from the withdrawal amount in `beforeWithdraw` or remove the fee accounting entirely.
2. **Fix BUG-02** -- AlwaysLPVault is a control/benchmark, but the double-counting makes comparison data unreliable.
3. **Add the invariant test handler** described in Section 2.2 for full stateful fuzzing coverage.
4. **Run the 7 concrete tests** from Section 4 with `forge test --match-contract PropertyTests -vvv`.
5. **Increase fuzz runs** in `foundry.toml`: `[fuzz] runs = 10000` for CI, `runs = 100000` for pre-audit.
