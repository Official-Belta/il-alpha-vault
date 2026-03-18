// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console} from "forge-std/Script.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {IHooks} from "v4-core/src/interfaces/IHooks.sol";
import {Hooks} from "v4-core/src/libraries/Hooks.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {PoolManager} from "v4-core/src/PoolManager.sol";
import {ILAlphaHook} from "../src/ILAlphaHook.sol";
import {ILAlphaVault} from "../src/ILAlphaVault.sol";
import {AlwaysLPVault} from "../src/controls/AlwaysLPVault.sol";
import {HODLVault} from "../src/controls/HODLVault.sol";
import {HookMiner} from "./HookMiner.sol";

/// @notice Deploy all IL Alpha Vault contracts to testnet
/// @dev Deploys its own PoolManager for testnet (V4 not yet on Sepolia).
///      Usage: source .env && forge script script/DeployAll.s.sol \
///        --rpc-url $RPC_URL --private-key $PRIVATE_KEY --broadcast
contract DeployAll is Script {

    function run() public {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("Deployer:", deployer);
        console.log("Balance:", deployer.balance);

        vm.startBroadcast(deployerPrivateKey);

        // ── Step 0: Deploy PoolManager ──
        // V4 is not yet deployed on Sepolia, so we deploy our own
        PoolManager pm = new PoolManager(deployer);
        address POOL_MANAGER = address(pm);
        console.log("PoolManager deployed:", POOL_MANAGER);

        vm.stopBroadcast();

        // ── Step 1: Mine and deploy Hook via CREATE2 ──
        uint160 flags = uint160(Hooks.AFTER_INITIALIZE_FLAG | Hooks.AFTER_SWAP_FLAG);

        address create2Deployer = 0x4e59b44847b379578588920cA78FbF26c0B4956C;
        bytes memory constructorArgs = abi.encode(IPoolManager(POOL_MANAGER));
        (bytes32 salt, address expectedHookAddr) = HookMiner.find(
            create2Deployer,
            flags,
            type(ILAlphaHook).creationCode,
            constructorArgs
        );
        console.log("Salt found:", uint256(salt));
        console.log("Expected hook address:", expectedHookAddr);

        vm.startBroadcast(deployerPrivateKey);

        ILAlphaHook hook = new ILAlphaHook{salt: salt}(IPoolManager(POOL_MANAGER));
        console.log("ILAlphaHook deployed:", address(hook));
        require(
            uint160(address(hook)) & uint160((1 << 14) - 1) == flags,
            "Hook address does not have correct permission flags"
        );

        // ── Step 3: Deploy mock tokens for testing ──
        // Deploy 2 mock ERC20 tokens (sorted by address)
        MockToken tokenA = new MockToken("Test USDC", "tUSDC", 6);
        MockToken tokenB = new MockToken("Test WETH", "tWETH", 18);

        // Sort tokens
        address token0Addr;
        address token1Addr;
        if (address(tokenA) < address(tokenB)) {
            token0Addr = address(tokenA);
            token1Addr = address(tokenB);
        } else {
            token0Addr = address(tokenB);
            token1Addr = address(tokenA);
        }
        console.log("Token0:", token0Addr);
        console.log("Token1:", token1Addr);

        // Mint test tokens
        MockToken(token0Addr).mint(deployer, 1_000_000 * 10**MockToken(token0Addr).decimals());
        MockToken(token1Addr).mint(deployer, 1_000_000 * 10**MockToken(token1Addr).decimals());

        // ── Step 4: Deploy ILAlphaVault ──
        ILAlphaVault vault = new ILAlphaVault(
            ERC20(token0Addr),
            IPoolManager(POOL_MANAGER),
            hook,
            "IL Alpha Vault",
            "ilALPHA"
        );
        console.log("ILAlphaVault deployed:", address(vault));

        // Set pool key on vault
        PoolKey memory poolKey = PoolKey({
            currency0: Currency.wrap(token0Addr),
            currency1: Currency.wrap(token1Addr),
            fee: 3000,
            tickSpacing: 60,
            hooks: IHooks(address(hook))
        });
        vault.setPoolKey(poolKey);

        // ── Step 5: Deploy Control Vaults ──
        AlwaysLPVault alwaysLPVault = new AlwaysLPVault(
            ERC20(token0Addr),
            "AlwaysLP Control Vault",
            "alwLP"
        );
        console.log("AlwaysLPVault deployed:", address(alwaysLPVault));

        HODLVault hodlVault = new HODLVault(
            ERC20(token0Addr),
            "HODL Control Vault",
            "HODL"
        );
        console.log("HODLVault deployed:", address(hodlVault));

        vm.stopBroadcast();

        // ── Summary ──
        console.log("=== DEPLOYMENT COMPLETE ===");
    }
}

/// @notice Simple mintable ERC20 for testnet
contract MockToken is ERC20 {
    constructor(string memory name, string memory symbol, uint8 decimals_)
        ERC20(name, symbol, decimals_)
    {}

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
