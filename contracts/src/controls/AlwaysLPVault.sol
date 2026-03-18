// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC4626} from "solmate/src/mixins/ERC4626.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {SafeTransferLib} from "solmate/src/utils/SafeTransferLib.sol";
import {FixedPointMathLib} from "solmate/src/utils/FixedPointMathLib.sol";

/// @title AlwaysLPVault
/// @notice Control vault: always provides LP regardless of vol conditions.
///         Used as benchmark to demonstrate ILAlpha's IL avoidance value.
///         Simplified: tracks "deployed" state but actual LP management is
///         handled by the same rebalance pattern as ILAlphaVault.
/// @dev For testnet comparison: deposit → always deploy → never withdraw LP unless user exits.
contract AlwaysLPVault is ERC4626 {
    using SafeTransferLib for ERC20;
    using FixedPointMathLib for uint256;

    uint256 internal constant VIRTUAL_SHARES = 1e6;
    uint256 internal constant VIRTUAL_ASSETS = 1e6;

    address public owner;
    uint256 public deployedAssets;

    error OnlyOwner();

    event Rebalanced(uint256 totalAssetsBefore, uint256 totalAssetsAfter);

    constructor(ERC20 _asset, string memory _name, string memory _symbol)
        ERC4626(_asset, _name, _symbol)
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

    /// @notice Always deploy idle assets as LP (control: always active)
    function rebalance() external {
        uint256 totalBefore = totalAssets();
        uint256 idle = asset.balanceOf(address(this));
        if (idle > 0) {
            // In a real implementation, this would call PoolManager.unlock → modifyLiquidity
            // For testnet control, we simulate by marking assets as deployed
            deployedAssets += idle;
            // Transfer to simulate deployment (in real version: V4 LP)
        }
        emit Rebalanced(totalBefore, totalAssets());
    }

    /// @notice Simulate LP removal for withdrawal
    function beforeWithdraw(uint256 assets, uint256) internal override {
        uint256 idle = asset.balanceOf(address(this));
        if (idle < assets && deployedAssets > 0) {
            // Pull all from LP
            deployedAssets = 0;
        }
    }
}
