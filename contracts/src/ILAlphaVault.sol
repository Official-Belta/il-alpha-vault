// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {SafeTransferLib} from "solmate/src/utils/SafeTransferLib.sol";
import {FixedPointMathLib} from "solmate/src/utils/FixedPointMathLib.sol";
import {BaseVault} from "./BaseVault.sol";
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
contract ILAlphaVault is BaseVault, IUnlockCallback {
    using SafeTransferLib for ERC20;
    using FixedPointMathLib for uint256;
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;
    using CurrencyLibrary for Currency;

    // ─── Errors ──────────────────────────────────────────────────────
    error OnlyOwner();
    error OnlyKeeper();
    error OnlyPoolManager();
    error Paused();
    error DepositTooSmall();
    error DepositCapExceeded();
    error Reentrancy();
    error InvalidPoolKey();
    error PriceManipulated();

    // ─── Events ──────────────────────────────────────────────────────
    event Rebalanced(
        bool lpActive,
        uint256 totalAssetsBefore,
        uint256 totalAssetsAfter,
        uint128 liquidityDelta,
        uint256 timestamp
    );
    event EmergencyWithdraw(uint256 amount);
    event OwnershipTransferStarted(address indexed currentOwner, address indexed pendingOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // ─── Storage ─────────────────────────────────────────────────────
    IPoolManager public immutable poolManager;
    ILAlphaHook public immutable hook;
    PoolKey public poolKey;

    address public owner;
    address public pendingOwner;
    address public keeper;
    bool public paused;
    bool private _locked;

    /// @notice Tracks the liquidity units deployed in the pool
    uint128 public deployedLiquidity;

    /// @notice Maximum total deposits allowed (default $10K USDC = 10_000e6)
    uint256 public depositCap = 10_000e6;

    /// @notice TWAP manipulation threshold (max tick deviation, default ±500 ticks ≈ ±5%)
    int24 public twapThreshold = 500;

    /// @notice Withdrawal fee in basis points (default 10 = 0.1%)
    uint256 public withdrawalFeeBps = 10;

    /// @notice Accumulated withdrawal fees (claimable by owner)
    uint256 public accumulatedFees;

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
    ) BaseVault(_asset, _name, _symbol) {
        poolManager = _poolManager;
        hook = _hook;
        owner = msg.sender;
        keeper = msg.sender;
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

    modifier onlyKeeper() {
        if (msg.sender != keeper && msg.sender != owner) revert OnlyKeeper();
        _;
    }

    modifier nonReentrant() {
        if (_locked) revert Reentrancy();
        _locked = true;
        _;
        _locked = false;
    }

    // ─── ERC-4626 Overrides ──────────────────────────────────────────

    /// @notice Total assets = idle balance + real-time LP value (not stale deployedAssets)
    /// @dev Uses LiquidityAmounts to compute current LP value based on pool tick.
    ///      This prevents the share price inflation bug (ref: Gamma hack Jan 2024, $6.4M).
    function totalAssets() public view override returns (uint256) {
        uint256 idle = asset.balanceOf(address(this));

        if (deployedLiquidity == 0) {
            return idle;
        }

        // Compute real-time value of deployed LP position
        (uint256 lpValue0, uint256 lpValue1) = _getDeployedLPValue();

        // Return idle + LP value in asset token terms
        // For simplicity, sum both token values (assumes ~1:1 for testnet pairs)
        // Production: use oracle for cross-token valuation
        return idle + lpValue0 + lpValue1;
    }

    function deposit(uint256 assets, address receiver)
        public
        override
        whenNotPaused
        nonReentrant
        returns (uint256 shares)
    {
        if (assets < VIRTUAL_ASSETS) revert DepositTooSmall();
        if (totalAssets() + assets > depositCap) revert DepositCapExceeded();
        _checkTWAP();
        shares = super.deposit(assets, receiver);
    }

    /// @notice ERC-4626 maxDeposit — enforces deposit cap
    function maxDeposit(address) public view override returns (uint256) {
        uint256 total = totalAssets();
        return total >= depositCap ? 0 : depositCap - total;
    }

    // ─── Rebalance ───────────────────────────────────────────────────

    /// @notice Rebalance vault: add/remove LP based on hook signal
    /// @dev Restricted to keeper/owner — prevents random callers from timing rebalances
    function rebalance() external onlyKeeper whenNotPaused nonReentrant {
        bool shouldLP = hook.isLPActive(poolKey);
        uint256 totalBefore = totalAssets();
        uint128 liquidityBefore = deployedLiquidity;

        if (shouldLP && deployedLiquidity == 0) {
            uint256 idleAssets = asset.balanceOf(address(this));
            if (idleAssets > 0) {
                _addLiquidity(idleAssets);
            }
        } else if (!shouldLP && deployedLiquidity > 0) {
            _removeLiquidity();
        }

        uint128 liquidityAfter = deployedLiquidity;
        uint128 liqDelta = liquidityAfter > liquidityBefore
            ? liquidityAfter - liquidityBefore
            : liquidityBefore - liquidityAfter;

        emit Rebalanced(shouldLP, totalBefore, totalAssets(), liqDelta, block.timestamp);
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

        (BalanceDelta delta,) = poolManager.modifyLiquidity(poolKey, params, "");

        // Settle negative deltas (vault owes tokens to pool)
        // Negative amount in delta = vault must pay that amount
        int128 d0 = delta.amount0();
        int128 d1 = delta.amount1();

        if (d0 < 0) _settleCurrency(poolKey.currency0, uint256(uint128(-d0)));
        if (d1 < 0) _settleCurrency(poolKey.currency1, uint256(uint128(-d1)));

        // Take positive deltas (pool owes tokens to vault) — e.g., fee credits
        if (d0 > 0) poolManager.take(poolKey.currency0, address(this), uint256(uint128(d0)));
        if (d1 > 0) poolManager.take(poolKey.currency1, address(this), uint256(uint128(d1)));

        deployedLiquidity += liquidity;
    }

    /// @dev Settle a currency debt: sync, transfer tokens to PoolManager, then settle
    function _settleCurrency(Currency currency, uint256 amount) internal {
        poolManager.sync(currency);
        ERC20(Currency.unwrap(currency)).safeTransfer(address(poolManager), amount);
        poolManager.settle();
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
    }

    // ─── Withdraw Hook ───────────────────────────────────────────────

    function beforeWithdraw(uint256 assets, uint256 /* shares */) internal override {
        _checkTWAP(); // Prevent withdrawal at manipulated price

        // Apply withdrawal fee (protects existing depositors from sandwich)
        if (withdrawalFeeBps > 0) {
            uint256 fee = (assets * withdrawalFeeBps) / 10_000;
            accumulatedFees += fee;
        }

        uint256 idle = asset.balanceOf(address(this));
        if (idle < assets && deployedLiquidity > 0) {
            _removeLiquidity();
        }
    }

    // ─── Internal: Real-time LP Valuation ────────────────────────────

    /// @dev Compute current value of deployed LP position using pool's current tick.
    ///      Replaces stale `deployedAssets` with live calculation.
    function _getDeployedLPValue() internal view returns (uint256 amount0, uint256 amount1) {
        PoolId poolId = poolKey.toId();
        (uint160 sqrtPriceX96,,,) = poolManager.getSlot0(poolId);

        if (sqrtPriceX96 == 0) return (0, 0);

        (,int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);

        uint160 sqrtPriceAX96 = TickMath.getSqrtPriceAtTick(tickLower);
        uint160 sqrtPriceBX96 = TickMath.getSqrtPriceAtTick(tickUpper);

        (amount0, amount1) = LiquidityAmounts.getAmountsForLiquidity(
            sqrtPriceX96, sqrtPriceAX96, sqrtPriceBX96, deployedLiquidity
        );
    }

    /// @dev Check that current spot price is within TWAP threshold.
    ///      Reverts if price appears manipulated (sandwich/flashloan attack).
    ///      Conservative threshold — Gamma's lax check led to $6.4M exploit.
    function _checkTWAP() internal view {
        if (deployedLiquidity == 0) return; // No position, no risk

        PoolId poolId = poolKey.toId();
        (uint160 sqrtPriceX96, int24 spotTick,,) = poolManager.getSlot0(poolId);

        if (sqrtPriceX96 == 0) return;

        // V4 doesn't have built-in observe() for TWAP, so we use the hook's
        // lastTick as a proxy for recent historical price
        (,int24 lastOracleTick,,) = hook.volOracles(poolId);

        // Check deviation: |spotTick - lastOracleTick| < threshold
        int24 deviation = spotTick > lastOracleTick
            ? spotTick - lastOracleTick
            : lastOracleTick - spotTick;

        if (deviation > twapThreshold) revert PriceManipulated();
    }

    // ─── View Functions ────────────────────────────────────────────────

    /// @notice Get comprehensive vault metrics for off-chain monitoring
    function getVaultMetrics()
        external
        view
        returns (
            uint256 totalAssetsVal,
            uint256 idleAssets,
            uint256 deployedValue,
            uint128 deployedLiquidityVal,
            uint256 sharePrice,
            bool lpActive,
            bool isPaused
        )
    {
        totalAssetsVal = totalAssets();
        idleAssets = asset.balanceOf(address(this));
        // Real-time LP value (not stale)
        if (deployedLiquidity > 0) {
            (uint256 v0, uint256 v1) = _getDeployedLPValue();
            deployedValue = v0 + v1;
        }
        deployedLiquidityVal = deployedLiquidity;
        uint256 oneShare = 10 ** decimals;
        sharePrice = convertToAssets(oneShare);
        lpActive = address(poolKey.hooks) != address(0)
            ? hook.isLPActive(poolKey)
            : false;
        isPaused = paused;
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
        // Validate that the asset token is one of the pool currencies
        address assetAddr = address(asset);
        if (
            Currency.unwrap(_poolKey.currency0) != assetAddr &&
            Currency.unwrap(_poolKey.currency1) != assetAddr
        ) revert InvalidPoolKey();
        poolKey = _poolKey;
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
    }

    function setKeeper(address _keeper) external onlyOwner {
        keeper = _keeper;
    }

    function setDepositCap(uint256 _cap) external onlyOwner {
        depositCap = _cap;
    }

    function setTwapThreshold(int24 _threshold) external onlyOwner {
        twapThreshold = _threshold;
    }

    function setWithdrawalFeeBps(uint256 _feeBps) external onlyOwner {
        require(_feeBps <= 100, "Max 1%"); // Cap at 1%
        withdrawalFeeBps = _feeBps;
    }

    function claimFees(address to) external onlyOwner {
        uint256 fees = accumulatedFees;
        accumulatedFees = 0;
        asset.safeTransfer(to, fees);
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
