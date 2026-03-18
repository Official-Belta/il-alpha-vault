// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC4626} from "solmate/src/mixins/ERC4626.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {FixedPointMathLib} from "solmate/src/utils/FixedPointMathLib.sol";

/// @title HODLVault
/// @notice Control vault: just holds the deposit token, never provides LP.
///         Used as benchmark — pure HODL returns with no LP activity.
///         This is the simplest ERC4626 vault possible.
contract HODLVault is ERC4626 {
    using FixedPointMathLib for uint256;

    uint256 internal constant VIRTUAL_SHARES = 1e6;
    uint256 internal constant VIRTUAL_ASSETS = 1e6;

    constructor(ERC20 _asset, string memory _name, string memory _symbol)
        ERC4626(_asset, _name, _symbol)
    {}

    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }

    function convertToShares(uint256 assets) public view override returns (uint256) {
        uint256 supply = totalSupply + VIRTUAL_SHARES;
        uint256 total = totalAssets() + VIRTUAL_ASSETS;
        return assets.mulDivDown(supply, total);
    }

    function convertToAssets(uint256 shares) public view override returns (uint256) {
        uint256 supply = totalSupply + VIRTUAL_SHARES;
        uint256 total = totalAssets() + VIRTUAL_ASSETS;
        return shares.mulDivDown(total, supply);
    }

    function previewDeposit(uint256 assets) public view override returns (uint256) {
        return convertToShares(assets);
    }

    function previewMint(uint256 shares) public view override returns (uint256) {
        uint256 supply = totalSupply + VIRTUAL_SHARES;
        uint256 total = totalAssets() + VIRTUAL_ASSETS;
        return shares.mulDivUp(total, supply);
    }

    function previewWithdraw(uint256 assets) public view override returns (uint256) {
        uint256 supply = totalSupply + VIRTUAL_SHARES;
        uint256 total = totalAssets() + VIRTUAL_ASSETS;
        return assets.mulDivUp(supply, total);
    }

    function previewRedeem(uint256 shares) public view override returns (uint256) {
        return convertToAssets(shares);
    }
}
