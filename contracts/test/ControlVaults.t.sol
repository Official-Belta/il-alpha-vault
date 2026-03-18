// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {MockERC20} from "solmate/src/test/utils/mocks/MockERC20.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {AlwaysLPVault} from "../src/controls/AlwaysLPVault.sol";
import {HODLVault} from "../src/controls/HODLVault.sol";

contract ControlVaultsTest is Test {
    MockERC20 token;
    AlwaysLPVault alwaysLP;
    HODLVault hodl;

    address alice = address(0xa11ce);
    address bob = address(0xb0b);

    function setUp() public {
        token = new MockERC20("Test USDC", "tUSDC", 6);
        alwaysLP = new AlwaysLPVault(ERC20(address(token)), "AlwaysLP", "aLP");
        hodl = new HODLVault(ERC20(address(token)), "HODL", "HODL");

        token.mint(address(this), 1_000_000e6);
        token.mint(alice, 1_000_000e6);
        token.mint(bob, 1_000_000e6);
    }

    // ─── HODLVault ───────────────────────────────────────────────────

    function test_hodl_deposit_withdraw() public {
        token.approve(address(hodl), 100e6);
        uint256 shares = hodl.deposit(100e6, address(this));
        assertTrue(shares > 0);

        uint256 before = token.balanceOf(address(this));
        hodl.redeem(shares, address(this), address(this));
        uint256 received = token.balanceOf(address(this)) - before;
        assertApproxEqRel(received, 100e6, 0.01e18);
    }

    function test_hodl_totalAssets_isIdleOnly() public {
        token.approve(address(hodl), 100e6);
        hodl.deposit(100e6, address(this));
        assertEq(hodl.totalAssets(), 100e6);
    }

    function test_hodl_multipleDepositors() public {
        vm.startPrank(alice);
        token.approve(address(hodl), 50e6);
        uint256 aliceShares = hodl.deposit(50e6, alice);
        vm.stopPrank();

        vm.startPrank(bob);
        token.approve(address(hodl), 50e6);
        uint256 bobShares = hodl.deposit(50e6, bob);
        vm.stopPrank();

        assertApproxEqRel(aliceShares, bobShares, 0.01e18);
    }

    // ─── AlwaysLPVault ───────────────────────────────────────────────

    function test_alwaysLP_deposit_withdraw() public {
        token.approve(address(alwaysLP), 100e6);
        uint256 shares = alwaysLP.deposit(100e6, address(this));
        assertTrue(shares > 0);

        uint256 before = token.balanceOf(address(this));
        alwaysLP.redeem(shares, address(this), address(this));
        uint256 received = token.balanceOf(address(this)) - before;
        assertApproxEqRel(received, 100e6, 0.01e18);
    }

    function test_alwaysLP_rebalance_tracksDeployment() public {
        token.approve(address(alwaysLP), 100e6);
        alwaysLP.deposit(100e6, address(this));
        assertEq(alwaysLP.deployedAssets(), 0);

        alwaysLP.rebalance();

        // Simulated deploy: tokens stay in vault, deployedAssets tracks "would be" deployed
        assertEq(alwaysLP.deployedAssets(), 100e6, "Should track deployed amount");
        // totalAssets = idle(100e6) + deployed(100e6) = 200e6 in simulation
        // (real V4 LP would move tokens out, making idle=0)
    }

    function test_alwaysLP_withdraw_noDeploy() public {
        token.approve(address(alwaysLP), 100e6);
        uint256 shares = alwaysLP.deposit(100e6, address(this));

        uint256 before = token.balanceOf(address(this));
        alwaysLP.redeem(shares, address(this), address(this));
        uint256 received = token.balanceOf(address(this)) - before;
        assertApproxEqRel(received, 100e6, 0.01e18);
    }

    function test_alwaysLP_rebalance_accumulates() public {
        token.approve(address(alwaysLP), 200e6);
        alwaysLP.deposit(100e6, address(this));

        alwaysLP.rebalance();
        assertEq(alwaysLP.deployedAssets(), 100e6);

        alwaysLP.deposit(100e6, address(this));
        alwaysLP.rebalance();
        // Simulated: idle includes first deposit's tokens (never moved) + second deposit
        // So rebalance adds all current idle (200e6) to deployed → 100+200=300
        assertEq(alwaysLP.deployedAssets(), 300e6, "Should accumulate all idle each rebalance");
    }

    // ─── Fuzz: Both vaults ───────────────────────────────────────────

    function testFuzz_hodl_roundTrip(uint256 amount) public {
        amount = bound(amount, 1e6, 1_000_000e6);
        token.approve(address(hodl), amount);
        uint256 shares = hodl.deposit(amount, address(this));

        uint256 before = token.balanceOf(address(this));
        hodl.redeem(shares, address(this), address(this));
        uint256 received = token.balanceOf(address(this)) - before;
        assertApproxEqRel(received, amount, 0.001e18);
    }

    function testFuzz_alwaysLP_roundTrip(uint256 amount) public {
        amount = bound(amount, 1e6, 1_000_000e6);
        token.approve(address(alwaysLP), amount);
        uint256 shares = alwaysLP.deposit(amount, address(this));

        uint256 before = token.balanceOf(address(this));
        alwaysLP.redeem(shares, address(this), address(this));
        uint256 received = token.balanceOf(address(this)) - before;
        assertApproxEqRel(received, amount, 0.001e18);
    }
}
