// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {BaseVault} from "../BaseVault.sol";

/// @title AlwaysLPVault
/// @notice Control vault: simulates always-on LP for benchmark comparison.
/// @dev H-6 FIX: no deployedAssets tracking — totalAssets = balance only.
///      This is a simulation vault. It doesn't actually deploy to V4.
///      "Rebalance" just emits an event for monitoring parity with ILAlphaVault.
contract AlwaysLPVault is BaseVault {
    address public owner;

    error OnlyOwner();
    event Rebalanced(uint256 totalAssets, uint256 timestamp);

    constructor(ERC20 _asset, string memory _name, string memory _symbol)
        BaseVault(_asset, _name, _symbol)
    {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert OnlyOwner();
        _;
    }

    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }

    /// @notice No-op rebalance (control vault: always "deployed")
    function rebalance() external {
        emit Rebalanced(totalAssets(), block.timestamp);
    }
}
