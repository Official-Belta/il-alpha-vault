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
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {ILAlphaHook} from "../src/ILAlphaHook.sol";
import {ILAlphaVault} from "../src/ILAlphaVault.sol";

contract ILAlphaVaultTest is Test {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    IPoolManager manager;
    PoolSwapTest swapRouter;
    PoolModifyLiquidityTest modifyLiquidityRouter;

    ILAlphaHook hook;
    ILAlphaVault vault;
    PoolKey poolKey;
    PoolId poolId;

    MockERC20 token0;
    MockERC20 token1;

    address alice = address(0xa11ce);
    address bob = address(0xb0b);

    uint160 constant SQRT_PRICE_1_1 = 79228162514264337593543950336;

    function setUp() public {
        manager = new PoolManager(address(this));
        swapRouter = new PoolSwapTest(manager);
        modifyLiquidityRouter = new PoolModifyLiquidityTest(manager);

        token0 = new MockERC20("Token0", "TKN0", 18);
        token1 = new MockERC20("Token1", "TKN1", 18);

        if (address(token0) > address(token1)) {
            (token0, token1) = (token1, token0);
        }

        // Mint tokens to test contract and users
        token0.mint(address(this), 10000 ether);
        token1.mint(address(this), 10000 ether);
        token0.mint(alice, 1000 ether);
        token1.mint(alice, 1000 ether);
        token0.mint(bob, 1000 ether);
        token1.mint(bob, 1000 ether);

        // Approve routers
        token0.approve(address(swapRouter), type(uint256).max);
        token1.approve(address(swapRouter), type(uint256).max);
        token0.approve(address(modifyLiquidityRouter), type(uint256).max);
        token1.approve(address(modifyLiquidityRouter), type(uint256).max);

        // Deploy hook
        uint160 flags = uint160(Hooks.AFTER_INITIALIZE_FLAG | Hooks.AFTER_SWAP_FLAG);
        address hookAddr = address(flags);
        deployCodeTo("ILAlphaHook.sol", abi.encode(manager), hookAddr);
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

        // Add initial pool liquidity
        modifyLiquidityRouter.modifyLiquidity(
            poolKey,
            IPoolManager.ModifyLiquidityParams({
                tickLower: -120,
                tickUpper: 120,
                liquidityDelta: 100 ether,
                salt: bytes32(0)
            }),
            ""
        );

        // Deploy vault with token0 as asset
        vault = new ILAlphaVault(
            ERC20(address(token0)),
            manager,
            hook,
            "IL Alpha Vault",
            "ilALPHA"
        );

        vault.setPoolKey(poolKey);
    }

    // ─── Deposit / Withdraw ──────────────────────────────────────────

    function test_deposit_basic() public {
        uint256 depositAmount = 100 ether;
        token0.approve(address(vault), depositAmount);

        uint256 shares = vault.deposit(depositAmount, address(this));
        assertTrue(shares > 0, "Should receive shares");
        assertEq(vault.balanceOf(address(this)), shares);
        assertEq(vault.totalAssets(), depositAmount);
    }

    function test_deposit_tooSmall_reverts() public {
        token0.approve(address(vault), 1);
        vm.expectRevert(ILAlphaVault.DepositTooSmall.selector);
        vault.deposit(1, address(this)); // < VIRTUAL_ASSETS (1e6)
    }

    function test_deposit_whenPaused_reverts() public {
        vault.setPaused(true);
        token0.approve(address(vault), 100 ether);
        vm.expectRevert(ILAlphaVault.Paused.selector);
        vault.deposit(100 ether, address(this));
    }

    function test_withdraw_basic() public {
        uint256 depositAmount = 100 ether;
        token0.approve(address(vault), depositAmount);
        uint256 shares = vault.deposit(depositAmount, address(this));

        uint256 balanceBefore = token0.balanceOf(address(this));
        vault.redeem(shares, address(this), address(this));
        uint256 balanceAfter = token0.balanceOf(address(this));

        // Should get back approximately the deposit amount (minus rounding)
        uint256 received = balanceAfter - balanceBefore;
        assertApproxEqRel(received, depositAmount, 0.01e18, "Should get back ~100% of deposit");
    }

    function test_multipleDepositors_fairShares() public {
        // Alice deposits first
        vm.startPrank(alice);
        token0.approve(address(vault), 100 ether);
        uint256 aliceShares = vault.deposit(100 ether, alice);
        vm.stopPrank();

        // Bob deposits same amount
        vm.startPrank(bob);
        token0.approve(address(vault), 100 ether);
        uint256 bobShares = vault.deposit(100 ether, bob);
        vm.stopPrank();

        // Shares should be approximately equal
        assertApproxEqRel(aliceShares, bobShares, 0.01e18, "Equal deposits should get equal shares");
    }

    // ─── Virtual Shares (Inflation Defense) ──────────────────────────

    function test_virtualShares_firstDepositor() public {
        // First depositor should not get disproportionate shares
        token0.approve(address(vault), 1e6); // minimum deposit
        uint256 shares = vault.deposit(1e6, address(this));
        assertTrue(shares > 0, "First depositor should get shares");

        // Verify share price is reasonable (not 1:1 due to virtual offset)
        uint256 assetsBack = vault.convertToAssets(shares);
        assertApproxEqAbs(assetsBack, 1e6, 1, "Should be able to redeem approximately what was deposited");
    }

    function test_virtualShares_inflationAttack() public {
        // Attacker deposits minimum
        token0.approve(address(vault), 2e6);
        vault.deposit(2e6, address(this));

        // Attacker tries to donate tokens directly to inflate share price
        token0.transfer(address(vault), 100 ether);

        // Victim deposits — should still get reasonable shares
        vm.startPrank(alice);
        token0.approve(address(vault), 10 ether);
        uint256 victimShares = vault.deposit(10 ether, alice);
        vm.stopPrank();

        assertTrue(victimShares > 0, "Victim should still get non-zero shares");

        // Victim should be able to get back a meaningful portion
        uint256 victimAssets = vault.convertToAssets(victimShares);
        assertTrue(victimAssets > 1 ether, "Victim should recover meaningful assets");
    }

    // ─── Rebalance ───────────────────────────────────────────────────

    function test_rebalance_noOpWhenInactive() public {
        token0.approve(address(vault), 100 ether);
        vault.deposit(100 ether, address(this));

        // LP is inactive by default, so rebalance should be a no-op
        vault.rebalance();

        assertEq(vault.deployedLiquidity(), 0, "Should not deploy LP when inactive");
        assertEq(vault.totalAssets(), 100 ether, "Total assets should not change");
    }

    function test_rebalance_whenPaused_reverts() public {
        vault.setPaused(true);
        vm.expectRevert(ILAlphaVault.Paused.selector);
        vault.rebalance();
    }

    // ─── Emergency ───────────────────────────────────────────────────

    function test_emergencyWithdraw_pauses() public {
        token0.approve(address(vault), 100 ether);
        vault.deposit(100 ether, address(this));

        vault.emergencyWithdraw();

        assertTrue(vault.paused(), "Should be paused after emergency");
    }

    function test_emergencyWithdraw_onlyOwner() public {
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaVault.OnlyOwner.selector);
        vault.emergencyWithdraw();
    }

    // ─── Access Control ──────────────────────────────────────────────

    function test_setPoolKey_onlyOwner() public {
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaVault.OnlyOwner.selector);
        vault.setPoolKey(poolKey);
    }

    function test_setPaused_onlyOwner() public {
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaVault.OnlyOwner.selector);
        vault.setPaused(true);
    }

    function test_twoStepOwnership() public {
        address newOwner = address(0xbeef);
        vault.transferOwnership(newOwner);

        assertEq(vault.owner(), address(this), "Owner should not change yet");
        assertEq(vault.pendingOwner(), newOwner);

        vm.prank(newOwner);
        vault.acceptOwnership();
        assertEq(vault.owner(), newOwner);
        assertEq(vault.pendingOwner(), address(0));
    }

    function test_twoStepOwnership_onlyPendingCanAccept() public {
        vault.transferOwnership(address(0xbeef));

        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaVault.OnlyOwner.selector);
        vault.acceptOwnership();
    }

    // ─── Reentrancy Guard ────────────────────────────────────────────

    function test_unlockCallback_onlyPoolManager() public {
        vm.prank(address(0xdead));
        vm.expectRevert(ILAlphaVault.OnlyPoolManager.selector);
        vault.unlockCallback("");
    }

    receive() external payable {}
}
