// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC4626} from "solmate/src/mixins/ERC4626.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {SafeTransferLib} from "solmate/src/utils/SafeTransferLib.sol";
import {FixedPointMathLib} from "solmate/src/utils/FixedPointMathLib.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {Currency, CurrencyLibrary} from "v4-core/src/types/Currency.sol";
import {BalanceDelta} from "v4-core/src/types/BalanceDelta.sol";
import {ILAlphaHook} from "./ILAlphaHook.sol";
import {IUnlockCallback} from "v4-core/src/interfaces/callback/IUnlockCallback.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {LiquidityAmounts} from "v4-core/test/utils/LiquidityAmounts.sol";

/// @title ILAlphaVault
/// @notice ERC-4626 vault that deposits into Uniswap V4 pools via ILAlphaHook.
///         Only provides liquidity when the hook signals positive expected value.
///         Implements virtual shares (1e6 offset) for inflation attack defense.
///
/// @dev Flow:
///   Depositor → deposit(USDC) → vault holds idle
///   Keeper    → rebalance()   → check hook.isLPActive()
///                              → if active:  unlock → addLiquidity
///                              → if inactive: unlock → removeLiquidity
///   Withdrawer → withdraw()   → pull from LP if needed → send USDC
contract ILAlphaVault is ERC4626, IUnlockCallback {
    using SafeTransferLib for ERC20;
    using FixedPointMathLib for uint256;
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;
    using CurrencyLibrary for Currency;

    // ─── Errors ──────────────────────────────────────────────────────
    error OnlyOwner();
    error OnlyPoolManager();
    error Paused();
    error DepositTooSmall();
    error Reentrancy();

    // ─── Events ──────────────────────────────────────────────────────
    event Rebalanced(bool lpActive, uint256 totalAssetsBefore, uint256 totalAssetsAfter);
    event EmergencyWithdraw(uint256 amount);
    event OwnershipTransferStarted(address indexed currentOwner, address indexed pendingOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // ─── Constants ───────────────────────────────────────────────────
    uint256 internal constant VIRTUAL_SHARES = 1e6;
    uint256 internal constant VIRTUAL_ASSETS = 1e6;

    // ─── Storage ─────────────────────────────────────────────────────
    IPoolManager public immutable poolManager;
    ILAlphaHook public immutable hook;
    PoolKey public poolKey;

    address public owner;
    address public pendingOwner;
    bool public paused;
    bool private _locked;

    /// @notice Amount of asset token currently deployed as LP in the V4 pool
    uint256 public deployedAssets;

    /// @notice Tracks the liquidity units deployed in the pool
    uint128 public deployedLiquidity;

    /// @notice Tracks pending unlock callback action
    enum CallbackAction { NONE, ADD_LIQUIDITY, REMOVE_LIQUIDITY }
    CallbackAction private _pendingAction;

    // ─── Constructor ─────────────────────────────────────────────────
    constructor(
        ERC20 _asset,
        IPoolManager _poolManager,
        ILAlphaHook _hook,
        string memory _name,
        string memory _symbol
    ) ERC4626(_asset, _name, _symbol) {
        poolManager = _poolManager;
        hook = _hook;
        owner = msg.sender;
    }

    // ─── Modifiers ───────────────────────────────────────────────────
    modifier onlyOwner() {
        if (msg.sender != owner) revert OnlyOwner();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert Paused();
        _;
    }

    modifier nonReentrant() {
        if (_locked) revert Reentrancy();
        _locked = true;
        _;
        _locked = false;
    }

    // ─── ERC-4626 Overrides ──────────────────────────────────────────

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

    function deposit(uint256 assets, address receiver)
        public
        override
        whenNotPaused
        nonReentrant
        returns (uint256 shares)
    {
        if (assets < VIRTUAL_ASSETS) revert DepositTooSmall();
        shares = super.deposit(assets, receiver);
    }

    // ─── Rebalance ───────────────────────────────────────────────────

    /// @notice Rebalance vault: add/remove LP based on hook signal
    function rebalance() external whenNotPaused nonReentrant {
        bool shouldLP = hook.isLPActive(poolKey);
        uint256 totalBefore = totalAssets();

        if (shouldLP && deployedLiquidity == 0) {
            uint256 idleAssets = asset.balanceOf(address(this));
            if (idleAssets > 0) {
                _addLiquidity(idleAssets);
            }
        } else if (!shouldLP && deployedLiquidity > 0) {
            _removeLiquidity();
        }

        emit Rebalanced(shouldLP, totalBefore, totalAssets());
    }

    function _addLiquidity(uint256 assets) internal {
        _pendingAction = CallbackAction.ADD_LIQUIDITY;
        poolManager.unlock(abi.encode(assets));
        _pendingAction = CallbackAction.NONE;
    }

    function _removeLiquidity() internal {
        _pendingAction = CallbackAction.REMOVE_LIQUIDITY;
        poolManager.unlock(abi.encode(uint256(0)));
        _pendingAction = CallbackAction.NONE;
    }

    /// @notice PoolManager unlock callback
    function unlockCallback(bytes calldata data) external override returns (bytes memory) {
        if (msg.sender != address(poolManager)) revert OnlyPoolManager();

        if (_pendingAction == CallbackAction.ADD_LIQUIDITY) {
            uint256 assets = abi.decode(data, (uint256));
            _executeAddLiquidity(assets);
        } else if (_pendingAction == CallbackAction.REMOVE_LIQUIDITY) {
            _executeRemoveLiquidity();
        }

        return "";
    }

    function _executeAddLiquidity(uint256 assets) internal {
        PoolId poolId = poolKey.toId();
        (uint160 sqrtPriceX96,,,) = poolManager.getSlot0(poolId);

        (,int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);

        uint160 sqrtPriceAX96 = TickMath.getSqrtPriceAtTick(tickLower);
        uint160 sqrtPriceBX96 = TickMath.getSqrtPriceAtTick(tickUpper);

        // Split assets 50/50 for two-sided LP (simplified for same-decimal pairs)
        uint256 amount0 = assets / 2;
        uint256 amount1 = assets / 2;

        // Compute proper liquidity from token amounts and price range
        uint128 liquidity = LiquidityAmounts.getLiquidityForAmounts(
            sqrtPriceX96, sqrtPriceAX96, sqrtPriceBX96, amount0, amount1
        );

        if (liquidity == 0) return;

        IPoolManager.ModifyLiquidityParams memory params = IPoolManager.ModifyLiquidityParams({
            tickLower: tickLower,
            tickUpper: tickUpper,
            liquidityDelta: int256(uint256(liquidity)),
            salt: bytes32(0)
        });

        // Sync both currencies before modifying liquidity
        poolManager.sync(poolKey.currency0);
        poolManager.sync(poolKey.currency1);

        // Approve both tokens
        ERC20(Currency.unwrap(poolKey.currency0)).approve(address(poolManager), amount0);
        ERC20(Currency.unwrap(poolKey.currency1)).approve(address(poolManager), amount1);

        poolManager.modifyLiquidity(poolKey, params, "");

        // Settle both currencies
        poolManager.settle();

        deployedLiquidity += liquidity;
        deployedAssets += assets;
    }

    function _executeRemoveLiquidity() internal {
        (,int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);

        IPoolManager.ModifyLiquidityParams memory params = IPoolManager.ModifyLiquidityParams({
            tickLower: tickLower,
            tickUpper: tickUpper,
            liquidityDelta: -int256(uint256(deployedLiquidity)),
            salt: bytes32(0)
        });

        (BalanceDelta delta,) = poolManager.modifyLiquidity(poolKey, params, "");

        // Take back tokens (positive delta = owed to caller)
        int128 d0 = delta.amount0();
        int128 d1 = delta.amount1();

        if (d0 > 0) poolManager.take(poolKey.currency0, address(this), uint256(uint128(d0)));
        if (d1 > 0) poolManager.take(poolKey.currency1, address(this), uint256(uint128(d1)));

        deployedLiquidity = 0;
        deployedAssets = 0;
    }

    // ─── Withdraw Hook ───────────────────────────────────────────────

    function beforeWithdraw(uint256 assets, uint256 /* shares */) internal override {
        uint256 idle = asset.balanceOf(address(this));
        if (idle < assets && deployedLiquidity > 0) {
            _removeLiquidity();
        }
    }

    // ─── Admin: Two-Step Ownership ───────────────────────────────────

    function transferOwnership(address newOwner) external onlyOwner {
        pendingOwner = newOwner;
        emit OwnershipTransferStarted(owner, newOwner);
    }

    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert OnlyOwner();
        emit OwnershipTransferred(owner, msg.sender);
        owner = msg.sender;
        pendingOwner = address(0);
    }

    function setPoolKey(PoolKey calldata _poolKey) external onlyOwner {
        poolKey = _poolKey;
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
    }

    /// @notice Emergency: pull all LP and pause
    function emergencyWithdraw() external onlyOwner nonReentrant {
        if (deployedLiquidity > 0) {
            _removeLiquidity();
        }
        paused = true;
        emit EmergencyWithdraw(asset.balanceOf(address(this)));
    }
}
