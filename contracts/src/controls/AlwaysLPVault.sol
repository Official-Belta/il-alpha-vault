// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {BaseVault} from "../BaseVault.sol";

/// @title AlwaysLPVault
/// @notice Control vault: always provides LP regardless of vol conditions.
///         Used as benchmark to demonstrate ILAlpha's IL avoidance value.
contract AlwaysLPVault is BaseVault {
    address public owner;
    uint256 public deployedAssets;

    error OnlyOwner();
    event Rebalanced(uint256 totalAssetsBefore, uint256 totalAssetsAfter);

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
        return asset.balanceOf(address(this)) + deployedAssets;
    }

    /// @notice Always deploy idle assets as LP (control: always active)
    function rebalance() external {
        uint256 totalBefore = totalAssets();
        uint256 idle = asset.balanceOf(address(this));
        if (idle > 0) {
            deployedAssets += idle;
        }
        emit Rebalanced(totalBefore, totalAssets());
    }

    function beforeWithdraw(uint256 assets, uint256) internal override {
        uint256 idle = asset.balanceOf(address(this));
        if (idle < assets && deployedAssets > 0) {
            deployedAssets = 0;
        }
    }
}
