// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console} from "forge-std/Script.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {IHooks} from "v4-core/src/interfaces/IHooks.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {ILAlphaVault} from "../src/ILAlphaVault.sol";
import {AlwaysLPVault} from "../src/controls/AlwaysLPVault.sol";
import {HODLVault} from "../src/controls/HODLVault.sol";
import {IUnlockCallback} from "v4-core/src/interfaces/callback/IUnlockCallback.sol";

/// @notice Initialize pool, add seed liquidity, fund all 3 vaults
/// @dev Run after DeployAll. Reads deployed addresses from env.
///      Usage: source .env && forge script script/SetupPool.s.sol:SetupPool \
///        --rpc-url $RPC_URL --private-key $PRIVATE_KEY --broadcast
contract SetupPool is Script, IUnlockCallback {
    // ── Deployed addresses (from DeployAll v2 output) ──
    address constant POOL_MANAGER_ADDR = 0x1AaEc1fFEe505326C5748c18EE6A680216927591;
    address constant HOOK_ADDR         = 0x7D4617B2Cc9b4CEc8db7F0d94342992a9FC95040;
    address constant VAULT_ADDR        = 0x1Bbb16bFe13b2C4165B57E303259F6298B170D73;
    address constant ALWAYS_LP_ADDR    = 0x245E285A79568891bA64b0DA06B8eF8345aB6F99;
    address constant HODL_ADDR         = 0x1cF63a6832d607C3447045aEB4B887cE4A36a0BF;
    address constant TOKEN0_ADDR       = 0x892C137DdDc63E703F78ac251A4a76b82B311a2b;
    address constant TOKEN1_ADDR       = 0xa49F6E602287cb3E2F67Ca7b79b9Cdd910E2cF03;

    IPoolManager poolManager = IPoolManager(POOL_MANAGER_ADDR);
    PoolKey poolKey;
    bool private _isAddingLiquidity;

    // 1:1 price (sqrtPriceX96 for price = 1.0)
    uint160 constant SQRT_PRICE_1_1 = 79228162514264337593543950336;

    // Vault funding amounts
    uint256 constant VAULT_FUND = 100_000e6; // 100K tUSDC (6 decimals)

    function run() public {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("Deployer:", deployer);

        // Build pool key
        poolKey = PoolKey({
            currency0: Currency.wrap(TOKEN0_ADDR),
            currency1: Currency.wrap(TOKEN1_ADDR),
            fee: 3000,
            tickSpacing: 60,
            hooks: IHooks(HOOK_ADDR)
        });

        vm.startBroadcast(deployerPrivateKey);

        // ── Step 1: Initialize pool ──
        console.log("Initializing pool...");
        int24 tick = poolManager.initialize(poolKey, SQRT_PRICE_1_1);
        console.log("Pool initialized at tick:", tick);

        // ── Step 2: Add seed liquidity via unlock callback ──
        console.log("Adding seed liquidity...");
        // Approve tokens to this contract (for settle pattern)
        ERC20(TOKEN0_ADDR).approve(address(this), type(uint256).max);
        ERC20(TOKEN1_ADDR).approve(address(this), type(uint256).max);

        _isAddingLiquidity = true;
        poolManager.unlock(abi.encode(deployer));
        _isAddingLiquidity = false;
        console.log("Seed liquidity added");

        // ── Step 3: Fund vaults ──
        console.log("Funding ILAlphaVault...");
        ERC20(TOKEN0_ADDR).approve(VAULT_ADDR, VAULT_FUND);
        ILAlphaVault(VAULT_ADDR).deposit(VAULT_FUND, deployer);

        console.log("Funding AlwaysLPVault...");
        ERC20(TOKEN0_ADDR).approve(ALWAYS_LP_ADDR, VAULT_FUND);
        AlwaysLPVault(ALWAYS_LP_ADDR).deposit(VAULT_FUND, deployer);

        console.log("Funding HODLVault...");
        ERC20(TOKEN0_ADDR).approve(HODL_ADDR, VAULT_FUND);
        HODLVault(HODL_ADDR).deposit(VAULT_FUND, deployer);

        vm.stopBroadcast();

        console.log("");
        console.log("=== SETUP COMPLETE ===");
        console.log("Pool: tUSDC/tWETH @ 1:1, fee=3000, tickSpacing=60");
        console.log("ILAlphaVault funded:", VAULT_FUND / 1e6, "tUSDC");
        console.log("AlwaysLPVault funded:", VAULT_FUND / 1e6, "tUSDC");
        console.log("HODLVault funded:", VAULT_FUND / 1e6, "tUSDC");
        console.log("======================");
    }

    /// @notice PoolManager unlock callback — add seed liquidity
    function unlockCallback(bytes calldata data) external returns (bytes memory) {
        require(msg.sender == POOL_MANAGER_ADDR, "only PM");
        address deployer = abi.decode(data, (address));

        // Add liquidity in a wide range
        IPoolManager.ModifyLiquidityParams memory params = IPoolManager.ModifyLiquidityParams({
            tickLower: -887220,
            tickUpper: 887220,
            liquidityDelta: 1e18,
            salt: bytes32(0)
        });

        poolManager.modifyLiquidity(poolKey, params, "");

        // Settle: transfer tokens to PM
        uint256 amount0 = 10_000e6;  // 10K tUSDC seed
        uint256 amount1 = 10_000e18; // 10K tWETH seed

        poolManager.sync(Currency.wrap(TOKEN0_ADDR));
        ERC20(TOKEN0_ADDR).transferFrom(deployer, POOL_MANAGER_ADDR, amount0);
        poolManager.settle();

        poolManager.sync(Currency.wrap(TOKEN1_ADDR));
        ERC20(TOKEN1_ADDR).transferFrom(deployer, POOL_MANAGER_ADDR, amount1);
        poolManager.settle();

        return "";
    }
}
