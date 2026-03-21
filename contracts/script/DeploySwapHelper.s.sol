// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console} from "forge-std/Script.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {SwapHelper} from "../src/SwapHelper.sol";

contract DeploySwapHelper is Script {
    // Arbitrum mainnet V4 PoolManager
    address constant POOL_MANAGER = 0x360E68faCcca8cA495c1B759Fd9EEe466db9FB32;

    function run() public {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        SwapHelper helper = new SwapHelper(IPoolManager(POOL_MANAGER));
        console.log("SwapHelper deployed:", address(helper));
        vm.stopBroadcast();
    }
}
