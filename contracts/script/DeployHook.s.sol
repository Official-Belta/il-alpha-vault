// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console} from "forge-std/Script.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {Hooks} from "v4-core/src/libraries/Hooks.sol";
import {ILAlphaHook} from "../src/ILAlphaHook.sol";
import {HookMiner} from "./HookMiner.sol";

/// @notice Deploy ILAlphaHook with CREATE2 address mining
/// @dev Usage: forge script script/DeployHook.s.sol --rpc-url $RPC_URL --broadcast
contract DeployHook is Script {
    // Set these before deploying
    address constant POOL_MANAGER = address(0); // TODO: set to actual PoolManager address

    function run() public {
        // Required flags: afterInitialize + afterSwap
        uint160 flags = uint160(Hooks.AFTER_INITIALIZE_FLAG | Hooks.AFTER_SWAP_FLAG);

        // Mine salt
        bytes memory constructorArgs = abi.encode(IPoolManager(POOL_MANAGER));
        (bytes32 salt, address expectedAddr) = HookMiner.find(
            msg.sender,
            flags,
            type(ILAlphaHook).creationCode,
            constructorArgs
        );

        console.log("Salt:", uint256(salt));
        console.log("Expected hook address:", expectedAddr);
        console.log("Flags check:", uint160(expectedAddr) & uint160((1 << 14) - 1) == flags);

        // Deploy
        vm.startBroadcast();
        ILAlphaHook hook = new ILAlphaHook{salt: salt}(IPoolManager(POOL_MANAGER));
        vm.stopBroadcast();

        require(address(hook) == expectedAddr, "Address mismatch");
        console.log("Hook deployed at:", address(hook));
    }
}
