// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console} from "forge-std/Script.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {IHooks} from "v4-core/src/interfaces/IHooks.sol";
import {Hooks} from "v4-core/src/libraries/Hooks.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {ILAlphaHook} from "../src/ILAlphaHook.sol";
import {ILAlphaVault} from "../src/ILAlphaVault.sol";
import {HookMiner} from "./HookMiner.sol";

/// @notice Deploy IL Alpha to Base Mainnet
/// @dev Connects to the real Uniswap V4 PoolManager on Base.
///      Does NOT deploy PoolManager or mock tokens — uses real USDC/WETH.
///
///      Usage:
///        export PRIVATE_KEY=0x...
///        export RPC_URL=https://mainnet.base.org
///        forge script script/DeployBase.s.sol:DeployBase \
///          --rpc-url $RPC_URL --private-key $PRIVATE_KEY --broadcast --verify
contract DeployBase is Script {
    // ── Base Mainnet Addresses ──
    address constant POOL_MANAGER = 0x498581fF718922c3f8e6A244956aF099B2652b2b;

    // Base mainnet USDC and WETH
    address constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;  // Base USDC
    address constant WETH = 0x4200000000000000000000000000000000000006;  // Base WETH

    function run() public {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("=== BASE MAINNET DEPLOYMENT ===");
        console.log("Deployer:", deployer);
        console.log("Balance:", deployer.balance);
        console.log("PoolManager:", POOL_MANAGER);

        // ── Step 1: Mine CREATE2 salt for hook ──
        uint160 flags = uint160(Hooks.AFTER_INITIALIZE_FLAG | Hooks.AFTER_SWAP_FLAG);
        address create2Deployer = 0x4e59b44847b379578588920cA78FbF26c0B4956C;
        bytes memory constructorArgs = abi.encode(IPoolManager(POOL_MANAGER), deployer);

        console.log("Mining CREATE2 salt...");
        (bytes32 salt, address expectedHookAddr) = HookMiner.find(
            create2Deployer,
            flags,
            type(ILAlphaHook).creationCode,
            constructorArgs
        );
        console.log("Salt:", uint256(salt));
        console.log("Expected hook:", expectedHookAddr);

        vm.startBroadcast(deployerPrivateKey);

        // ── Step 2: Deploy Hook ──
        ILAlphaHook hook = new ILAlphaHook{salt: salt}(IPoolManager(POOL_MANAGER), deployer);
        console.log("ILAlphaHook:", address(hook));
        require(
            uint160(address(hook)) & uint160((1 << 14) - 1) == flags,
            "Hook address flags mismatch"
        );

        // ── Step 3: Deploy Vault ──
        // Sort tokens: USDC and WETH — need to check which is currency0
        address token0 = USDC < WETH ? USDC : WETH;
        address token1 = USDC < WETH ? WETH : USDC;

        // Vault asset = USDC (depositors deposit USDC)
        ILAlphaVault vault = new ILAlphaVault(
            ERC20(USDC),
            IPoolManager(POOL_MANAGER),
            hook,
            "IL Alpha Vault",
            "ilALPHA"
        );
        console.log("ILAlphaVault:", address(vault));

        // Set pool key (ETH/USDC, 0.3% fee, 60 tick spacing)
        PoolKey memory poolKey = PoolKey({
            currency0: Currency.wrap(token0),
            currency1: Currency.wrap(token1),
            fee: 3000,
            tickSpacing: 60,
            hooks: IHooks(address(hook))
        });
        vault.setPoolKey(poolKey);

        vm.stopBroadcast();

        console.log("");
        console.log("=== DEPLOYMENT COMPLETE ===");
        console.log("Network:      Base Mainnet (Chain 8453)");
        console.log("PoolManager:  ", POOL_MANAGER);
        console.log("ILAlphaHook:  ", address(hook));
        console.log("ILAlphaVault: ", address(vault));
        console.log("Token0:       ", token0);
        console.log("Token1:       ", token1);
        console.log("Pool fee:      3000 (0.3%)");
        console.log("Owner:        ", deployer);
        console.log("");
        console.log("NEXT STEPS:");
        console.log("1. Deposit USDC: vault.deposit(amount, yourAddress)");
        console.log("2. Set keeper: hook.setKeeper(keeperAddress)");
        console.log("3. Start keeper bot with --rpc-url https://mainnet.base.org");
    }
}
