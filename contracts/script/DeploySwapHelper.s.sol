// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console} from "forge-std/Script.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {SwapHelper} from "../src/SwapHelper.sol";

contract DeploySwapHelper is Script {
    address constant POOL_MANAGER = 0x53Bb7B0C806dC304F55b911A5A7A09b1817E794F;

    function run() public {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        SwapHelper helper = new SwapHelper(IPoolManager(POOL_MANAGER));
        console.log("SwapHelper deployed:", address(helper));
        vm.stopBroadcast();
    }
}
