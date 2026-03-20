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

/// @notice Deploy IL Alpha to Arbitrum Mainnet
/// @dev Connects to the real Uniswap V4 PoolManager on Arbitrum.
///      Uses real USDC and WETH. CEO seed: $1K USDC.
///
///      Usage:
///        export PRIVATE_KEY=0x...
///        export RPC_URL=https://arb1.arbitrum.io/rpc
///        cd contracts
///        forge script script/DeployArbitrum.s.sol:DeployArbitrum \
///          --rpc-url $RPC_URL --private-key $PRIVATE_KEY --broadcast
contract DeployArbitrum is Script {
    // ── Arbitrum Mainnet Addresses ──
    address constant POOL_MANAGER = 0x360E68faCcca8cA495c1B759Fd9EEe466db9FB32;

    // Arbitrum mainnet tokens
    address constant USDC  = 0xaf88d065e77c8cC2239327C5EDb3A432268e5831;  // Arbitrum native USDC
    address constant WETH  = 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1;  // Arbitrum WETH

    function run() public {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("=== ARBITRUM MAINNET DEPLOYMENT ===");
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
        // Sort tokens
        address token0 = USDC < WETH ? USDC : WETH;
        address token1 = USDC < WETH ? WETH : USDC;

        // Vault asset = USDC
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

        // Arb C-2: register vault on hook for deployedLiquidity check
        hook.setVault(address(vault));

        vm.stopBroadcast();

        console.log("");
        console.log("=== DEPLOYMENT COMPLETE ===");
        console.log("Network:      Arbitrum Mainnet (Chain 42161)");
        console.log("PoolManager:  ", POOL_MANAGER);
        console.log("ILAlphaHook:  ", address(hook));
        console.log("ILAlphaVault: ", address(vault));
        console.log("Token0:       ", token0);
        console.log("Token1:       ", token1);
        console.log("Pool fee:      3000 (0.3%)");
        console.log("Deposit cap:   10,000 USDC");
        console.log("Owner:        ", deployer);
        console.log("");
        console.log("=== SECURITY CHECKLIST (do ALL before depositing) ===");
        console.log("1. Create SEPARATE keeper wallet (new EOA)");
        console.log("2. hook.setKeeper(keeperAddress)");
        console.log("3. vault.setKeeper(keeperAddress)");
        console.log("4. Fund keeper wallet with ~0.001 ETH for gas");
        console.log("5. Transfer ownership to Gnosis Safe multi-sig:");
        console.log("   hook.transferOwnership(safeAddress)");
        console.log("   vault.transferOwnership(safeAddress)");
        console.log("   Then from Safe: hook.acceptOwnership() + vault.acceptOwnership()");
        console.log("6. ONLY THEN: vault.deposit(amount, yourAddress)");
        console.log("");
        console.log("=== KEEPER SETUP ===");
        console.log("python keeper/keeper.py \\");
        console.log("  --rpc-url https://arb1.arbitrum.io/rpc \\");
        console.log("  --hook-address", address(hook), "\\");
        console.log("  --vault-address", address(vault), "\\");
        console.log("  --pool-key keeper/pool_key.json \\");
        console.log("  --symbol ETHUSDC --interval 3600");
    }
}
