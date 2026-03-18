// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {BaseVault} from "../BaseVault.sol";

/// @title HODLVault
/// @notice Control vault: just holds the deposit token, never provides LP.
///         Used as benchmark — pure HODL returns with no LP activity.
contract HODLVault is BaseVault {
    constructor(ERC20 _asset, string memory _name, string memory _symbol)
        BaseVault(_asset, _name, _symbol)
    {}

    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }
}
