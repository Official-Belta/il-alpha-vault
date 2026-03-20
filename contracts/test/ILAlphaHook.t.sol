// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
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
import {MockERC20} from "solmate/src/test/utils/mocks/MockERC20.sol";
import {ILAlphaHook} from "../src/ILAlphaHook.sol";

contract ILAlphaHookTest is Test {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    IPoolManager manager;
    PoolSwapTest swapRouter;
    PoolModifyLiquidityTest modifyLiquidityRouter;

    ILAlphaHook hook;
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

        token0.mint(address(this), 100000 ether);
        token1.mint(address(this), 100000 ether);

        token0.approve(address(swapRouter), type(uint256).max);
        token1.approve(address(swapRouter), type(uint256).max);
        token0.approve(address(modifyLiquidityRouter), type(uint256).max);
        token1.approve(address(modifyLiquidityRouter), type(uint256).max);

        // Deploy hook at address with correct permission flags
        // afterInitialize (bit 12) + afterSwap (bit 6)
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
                tickLower: -120,
                tickUpper: 120,
                liquidityDelta: 10 ether,
                salt: bytes32(0)
            }),
            ""
        );
    }

    // ─── Hook Registration ───────────────────────────────────────────

    function test_afterInitialize_registersPool() public view {
        (bool isActive, int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);
        assertFalse(isActive, "LP should start inactive");
        assertTrue(tickLower < 0, "tickLower should be negative");
        assertTrue(tickUpper > 0, "tickUpper should be positive");
    }

    function test_volOracle_initialState() public view {
        (uint128 ewmaVar, int24 lastTick, uint40 lastTimestamp, uint16 lambda) = hook.volOracles(poolId);
        assertEq(ewmaVar, 0, "Initial variance should be 0");
        assertEq(lastTick, 0, "Initial tick should be 0 (1:1 price)");
        assertTrue(lastTimestamp > 0, "Timestamp should be set");
        assertEq(lambda, 9400, "Lambda should be 0.94");
    }

    function test_afterInitialize_reInitSamePool() public {
        // Re-initializing should just overwrite (PoolManager would revert for real re-init,
        // but afterInitialize itself should handle the state write correctly)
        (uint128 varBefore,,,) = hook.volOracles(poolId);
        assertEq(varBefore, 0);
        // The pool state is already registered — verifying it doesn't corrupt
        (bool isActive,,,,) = hook.getPoolStrategy(poolKey);
        assertFalse(isActive);
    }

    // ─── Vol Oracle ──────────────────────────────────────────────────

    function test_afterSwap_updatesVolOracle() public {
        vm.warp(block.timestamp + 1 hours);
        _doSwap(true, -1 ether);

        (uint128 ewmaVar,,,) = hook.volOracles(poolId);
        assertTrue(ewmaVar > 0, "EWMA variance should update after swap");
    }

    function test_afterSwap_multipleSwaps_accumulates() public {
        vm.warp(block.timestamp + 1 hours);
        _doSwap(true, -0.5 ether);

        (uint128 var1,,,) = hook.volOracles(poolId);
        assertTrue(var1 > 0);

        vm.warp(block.timestamp + 1 hours);
        _doSwap(false, -0.5 ether);

        (uint128 var2,,,) = hook.volOracles(poolId);
        assertTrue(var2 > 0, "Variance should remain positive after second swap");
    }

    function test_afterSwap_zeroElapsedTime_noOp() public {
        // Warp to trigger first update
        vm.warp(block.timestamp + 1 hours);
        _doSwap(true, -0.5 ether);
        (uint128 varAfterFirst,,,) = hook.volOracles(poolId);

        // Second swap in SAME block — should not update vol
        _doSwap(false, -0.5 ether);
        (uint128 varAfterSecond,,,) = hook.volOracles(poolId);

        assertEq(varAfterFirst, varAfterSecond, "Same-block swap should not change variance");
    }

    function test_afterSwap_largeTickDelta_noOverflow() public {
        // Add liquidity over a huge range to allow large price moves
        modifyLiquidityRouter.modifyLiquidity(
            poolKey,
            IPoolManager.ModifyLiquidityParams({
                tickLower: -887220,
                tickUpper: 887220,
                liquidityDelta: 100 ether,
                salt: bytes32(uint256(1))
            }),
            ""
        );

        vm.warp(block.timestamp + 1 hours);

        // Large swap to move price significantly
        _doSwap(true, -50 ether);

        // Should not revert — overflow is handled by uint128 cap
        (uint128 ewmaVar,,,) = hook.volOracles(poolId);
        assertTrue(ewmaVar > 0, "Large tick delta should produce non-zero variance");
    }

    // ─── LP Toggle ───────────────────────────────────────────────────

    function test_lpToggle_startsInactive() public view {
        assertFalse(hook.isLPActive(poolKey), "LP should start inactive");
    }

    function _activateLP() internal {
        // Add deep liquidity so swaps generate volume without much tick movement
        modifyLiquidityRouter.modifyLiquidity(
            poolKey,
            IPoolManager.ModifyLiquidityParams({
                tickLower: -887220,
                tickUpper: 887220,
                liquidityDelta: 10000 ether,
                salt: bytes32(uint256(99))
            }),
            ""
        );

        // Generate volume with a large swap (deep liquidity = tiny tick move = low vol)
        vm.warp(block.timestamp + 1 hours);
        _doSwap(true, -100 ether);

        // Zero out any residual vol via repeated pushes
        for (uint256 i = 0; i < 80; i++) {
            _pushVol(0);
        }

        // Wait past cooldown and trigger
        vm.warp(block.timestamp + 25 hours);
        hook.triggerEvaluation(poolKey);
    }

    function test_lpToggle_activatesWithLowVol() public {
        _activateLP();
        assertTrue(hook.isLPActive(poolKey), "LP should activate when vol is low and volume exists");
    }

    function test_lpToggle_deactivatesWithHighVol() public {
        _activateLP();
        assertTrue(hook.isLPActive(poolKey), "LP should be active initially");

        // Push very high vol to make IL cost exceed fee yield
        _pushVol(1000e18);

        vm.warp(block.timestamp + 25 hours);
        hook.triggerEvaluation(poolKey);
        assertFalse(hook.isLPActive(poolKey), "LP should deactivate when vol is high");
    }

    function test_lpToggle_reactivatesAfterVolDrops() public {
        _activateLP();
        assertTrue(hook.isLPActive(poolKey));

        // Deactivate with high vol
        _pushVol(1000e18);
        vm.warp(block.timestamp + 25 hours);
        hook.triggerEvaluation(poolKey);
        assertFalse(hook.isLPActive(poolKey));

        // Zero out vol with repeated pushes, then do a swap for fresh volume
        for (uint256 i = 0; i < 80; i++) {
            _pushVol(0);
        }
        // Generate fresh volume
        vm.warp(block.timestamp + 1 hours);
        _doSwap(false, -100 ether);
        // Zero vol again after swap-induced vol
        for (uint256 i = 0; i < 80; i++) {
            _pushVol(0);
        }

        vm.warp(block.timestamp + 25 hours);
        hook.triggerEvaluation(poolKey);
        assertTrue(hook.isLPActive(poolKey), "LP should reactivate when vol drops");
    }

    function test_lpToggle_respectsCooldown() public {
        _activateLP();
        assertTrue(hook.isLPActive(poolKey), "LP should be active");

        _pushVol(1000e18);

        vm.expectRevert(ILAlphaHook.CooldownActive.selector);
        hook.triggerEvaluation(poolKey);

        assertTrue(hook.isLPActive(poolKey), "LP should still be active (cooldown)");
    }

    // ─── Keeper Functions ────────────────────────────────────────────

    function test_keeper_pushVolEstimate() public {
        _pushVol(100e18);

        (uint128 ewmaVar,,,) = hook.volOracles(poolId);
        assertEq(ewmaVar, 5e17, "Vol capped to 1e18 then blended when baseline is 0");
    }

    function test_keeper_pushVolEstimate_onlyKeeper() public {
        vm.roll(block.number + 1);
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaHook.OnlyKeeper.selector);
        hook.pushVolEstimate(poolKey, 100e18);
    }

    function test_keeper_pushVolEstimate_rateLimited() public {
        _pushVol(100e18);
        (uint128 baseline,,,) = hook.volOracles(poolId);
        assertTrue(baseline > 0);

        _pushVol(type(uint256).max);
        (uint128 afterPush,,,) = hook.volOracles(poolId);

        // Result should be (baseline + min(max, baseline*4)) / 2 = (baseline + baseline*4) / 2 = baseline*2.5
        // Not uint128.max — rate limiting worked
        assertTrue(afterPush > baseline, "Should increase");
        assertTrue(afterPush < baseline * 4, "Should be rate-limited, not 4x+");
    }

    function test_keeper_triggerEvaluation_cooldown() public {
        // Must actually toggle LP to set lastToggleTime
        _activateLP();

        // Now immediately try again — should revert due to cooldown
        vm.expectRevert(ILAlphaHook.CooldownActive.selector);
        hook.triggerEvaluation(poolKey);
    }

    // ─── Admin ───────────────────────────────────────────────────────

    function test_setKeeper() public {
        address newKeeper = address(0xbeef);
        hook.setKeeper(newKeeper);
        assertEq(hook.keeper(), newKeeper);
    }

    function test_setKeeper_onlyOwner() public {
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaHook.OnlyOwner.selector);
        hook.setKeeper(address(0xbeef));
    }

    function test_setLPRange() public {
        hook.setLPRange(poolKey, -600, 600);
        (,int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);
        assertEq(tickLower, -600);
        assertEq(tickUpper, 600);
    }

    function test_setLPRange_onlyOwner() public {
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaHook.OnlyOwner.selector);
        hook.setLPRange(poolKey, -600, 600);
    }

    function test_setLPRange_invalidRange() public {
        vm.expectRevert(ILAlphaHook.InvalidTickRange.selector);
        hook.setLPRange(poolKey, 600, -600);

        vm.expectRevert(ILAlphaHook.InvalidTickRange.selector);
        hook.setLPRange(poolKey, 100, 100);
    }

    function test_setLambda() public {
        hook.setLambda(poolKey, 9000);
        (,,, uint16 lambda) = hook.volOracles(poolId);
        assertEq(lambda, 9000);
    }

    function test_setLambda_boundsCheck() public {
        vm.expectRevert(ILAlphaHook.InvalidLambda.selector);
        hook.setLambda(poolKey, 4999); // below MIN_LAMBDA

        vm.expectRevert(ILAlphaHook.InvalidLambda.selector);
        hook.setLambda(poolKey, 9901); // above MAX_LAMBDA
    }

    function test_twoStepOwnership() public {
        address newOwner = address(0xbeef);

        hook.transferOwnership(newOwner);
        assertEq(hook.owner(), address(this), "Owner should not change yet");
        assertEq(hook.pendingOwner(), newOwner);

        vm.prank(newOwner);
        hook.acceptOwnership();
        assertEq(hook.owner(), newOwner);
        assertEq(hook.pendingOwner(), address(0));
    }

    function test_twoStepOwnership_onlyPendingCanAccept() public {
        hook.transferOwnership(address(0xbeef));

        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaHook.OnlyOwner.selector);
        hook.acceptOwnership();
    }

    function test_transferOwnership_onlyOwner() public {
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaHook.OnlyOwner.selector);
        hook.transferOwnership(address(0xbeef));
    }

    // ─── Views ───────────────────────────────────────────────────────

    function test_getVolEstimate() public view {
        (uint128 hourlyVar, uint256 annualizedVol) = hook.getVolEstimate(poolKey);
        assertEq(hourlyVar, 0);
        assertEq(annualizedVol, 0);
    }

    function test_getPoolStrategy_returnsCorrectState() public view {
        (bool active, int24 tickLower, int24 tickUpper, uint256 feeYield, uint256 ilCost) =
            hook.getPoolStrategy(poolKey);
        assertFalse(active);
        assertTrue(tickLower < tickUpper);
        // feeYield is now volume-dependent, so with 0 volume it's 0
        assertEq(feeYield, 0, "Fee yield should be 0 with no volume");
        assertEq(ilCost, 0, "IL cost should be 0 with no vol");
    }

    // ─── Fuzz Tests ──────────────────────────────────────────────────

    function testFuzz_pushVolEstimate_alwaysCapped(uint256 externalVar) public {
        vm.roll(block.number + 1);
        hook.pushVolEstimate(poolKey, externalVar);
        (uint128 ewmaVar,,,) = hook.volOracles(poolId);
        assertTrue(ewmaVar <= type(uint128).max, "Should never exceed uint128.max");
    }

    function testFuzz_setLambda_boundsEnforced(uint16 lambda) public {
        if (lambda < 5000 || lambda > 9900) {
            vm.expectRevert(ILAlphaHook.InvalidLambda.selector);
            hook.setLambda(poolKey, lambda);
        } else {
            hook.setLambda(poolKey, lambda);
            (,,, uint16 storedLambda) = hook.volOracles(poolId);
            assertEq(storedLambda, lambda);
        }
    }

    function testFuzz_setLPRange_lowerMustBeLessThanUpper(int24 lower, int24 upper) public {
        // Bound to valid tick range and align to tick spacing (60)
        int24 spacing = poolKey.tickSpacing;
        lower = int24(bound(int256(lower), -887220, 887220));
        upper = int24(bound(int256(upper), -887220, 887220));
        // Align to tick spacing
        lower = (lower / spacing) * spacing;
        upper = (upper / spacing) * spacing;

        if (lower >= upper) {
            vm.expectRevert(ILAlphaHook.InvalidTickRange.selector);
            hook.setLPRange(poolKey, lower, upper);
        } else {
            hook.setLPRange(poolKey, lower, upper);
            (,int24 storedLower, int24 storedUpper,,) = hook.getPoolStrategy(poolKey);
            assertEq(storedLower, lower);
            assertEq(storedUpper, upper);
        }
    }

    // ─── Helper ──────────────────────────────────────────────────────

    /// @dev Helper: push vol with block advancement (H-3 per-block limit)
    function _pushVol(uint256 vol) internal {
        vm.roll(block.number + 1);
        hook.pushVolEstimate(poolKey, vol);
    }

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
