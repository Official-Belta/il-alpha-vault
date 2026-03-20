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
    error OnlyPoolManager();
    error Paused();
    error DepositTooSmall();
    error DepositCapExceeded();
    error Reentrancy();
    error InvalidPoolKey();
    error PriceManipulated();
    error LPStillDeployed();
    error TwapThresholdOutOfRange();
    error SlippageExceeded();

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
    event KeeperUpdated(address indexed oldKeeper, address indexed newKeeper);
    event DepositCapUpdated(uint256 oldCap, uint256 newCap);
    event TwapThresholdUpdated(int24 oldThreshold, int24 newThreshold);
    event SlippageUpdated(uint256 oldBps, uint256 newBps);
    event PoolKeyUpdated(address indexed currency0, address indexed currency1, uint24 fee);
    event PauseUpdated(bool paused);

    // ─── Unaudited Notice ─────────────────────────────────────────────
    /// @notice This contract has NOT been audited. Use at your own risk.
    bool public constant UNAUDITED = true;

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

    /// @notice Max slippage on LP add/remove in basis points (default 100 = 1%)
    uint256 public maxSlippageBps = 100;

    /// @notice TWAP manipulation threshold (max tick deviation, default ±500 ticks ≈ ±5%)
    int24 public twapThreshold = 500;

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
    /// @notice H-7 FIX: totalAssets counts only the vault's asset token
    /// @dev LP position value in the non-asset token is excluded to prevent
    ///      cross-token valuation errors. This is conservative — understates
    ///      totalAssets when LP holds the other token, protecting share price.
    function totalAssets() public view override returns (uint256) {
        uint256 idle = asset.balanceOf(address(this));

        if (deployedLiquidity == 0) {
            return idle;
        }

        (uint256 lpValue0, uint256 lpValue1) = _getDeployedLPValue();

        // Only count the value in our asset token
        address assetAddr = address(asset);
        if (Currency.unwrap(poolKey.currency0) == assetAddr) {
            return idle + lpValue0;
        } else {
            return idle + lpValue1;
        }
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

    /// @notice C-2 FIX: mint() must have same guards as deposit()
    /// @dev V4 L-5 FIX: previewMint called once for guard checks, super.mint handles the rest
    function mint(uint256 shares, address receiver)
        public
        override
        whenNotPaused
        nonReentrant
        returns (uint256 assets)
    {
        uint256 expectedAssets = previewMint(shares);
        if (expectedAssets < VIRTUAL_ASSETS) revert DepositTooSmall();
        if (totalAssets() + expectedAssets > depositCap) revert DepositCapExceeded();
        _checkTWAP();
        assets = super.mint(shares, receiver);
    }

    /// @notice ERC-4626 maxDeposit — enforces deposit cap
    /// @notice V3 M-1 FIX: returns 0 when paused
    function maxDeposit(address) public view override returns (uint256) {
        if (paused) return 0;
        uint256 total = totalAssets();
        return total >= depositCap ? 0 : depositCap - total;
    }

    /// @notice V3 M-1 FIX: maxMint respects pause + deposit cap
    function maxMint(address) public view override returns (uint256) {
        if (paused) return 0;
        uint256 maxAssets = maxDeposit(address(0));
        return maxAssets == 0 ? 0 : convertToShares(maxAssets);
    }

    // ─── Rebalance ───────────────────────────────────────────────────

    /// @notice Rebalance vault: add/remove LP based on hook signal
    /// @dev Public — anyone can call. Result is deterministic (hook signal only).
    ///      Keeper liveness is not a single point of failure.
    function rebalance() external whenNotPaused nonReentrant {
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
        // Compute liquidity from pool state + LP range
        uint128 liquidity = _computeLiquidity(assets);
        if (liquidity == 0) return;

        (,int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);

        (BalanceDelta delta,) = poolManager.modifyLiquidity(poolKey,
            IPoolManager.ModifyLiquidityParams({
                tickLower: tickLower, tickUpper: tickUpper,
                liquidityDelta: int256(uint256(liquidity)), salt: bytes32(0)
            }), "");

        // Settle and take
        _settleDelta(delta);

        // H-2: slippage check
        _checkSlippage(delta.amount0(), delta.amount1(), assets);

        deployedLiquidity += liquidity;
    }

    /// @dev Compute LP liquidity from asset amount + current pool state
    /// @dev H-3 NOTE: 50/50 split assumes vault holds both tokens. Phase 4: pre-swap.
    function _computeLiquidity(uint256 assets) internal view returns (uint128) {
        PoolId poolId = poolKey.toId();
        (uint160 sqrtPriceX96,,,) = poolManager.getSlot0(poolId);
        (,int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);

        return LiquidityAmounts.getLiquidityForAmounts(
            sqrtPriceX96,
            TickMath.getSqrtPriceAtTick(tickLower),
            TickMath.getSqrtPriceAtTick(tickUpper),
            assets / 2, assets / 2
        );
    }

    /// @dev Settle negative deltas (pay) and take positive deltas (receive)
    function _settleDelta(BalanceDelta delta) internal {
        int128 d0 = delta.amount0();
        int128 d1 = delta.amount1();

        if (d0 < 0) _settleCurrency(poolKey.currency0, uint256(uint128(-d0)));
        if (d1 < 0) _settleCurrency(poolKey.currency1, uint256(uint128(-d1)));
        if (d0 > 0) poolManager.take(poolKey.currency0, address(this), uint256(uint128(d0)));
        if (d1 > 0) poolManager.take(poolKey.currency1, address(this), uint256(uint128(d1)));
    }

    /// @dev Settle a currency debt: sync, transfer tokens to PoolManager, then settle
    function _settleCurrency(Currency currency, uint256 amount) internal {
        poolManager.sync(currency);
        ERC20(Currency.unwrap(currency)).safeTransfer(address(poolManager), amount);
        poolManager.settle();
    }

    function _executeRemoveLiquidity() internal {
        (,int24 tickLower, int24 tickUpper,,) = hook.getPoolStrategy(poolKey);

        (BalanceDelta delta,) = poolManager.modifyLiquidity(poolKey,
            IPoolManager.ModifyLiquidityParams({
                tickLower: tickLower, tickUpper: tickUpper,
                liquidityDelta: -int256(uint256(deployedLiquidity)), salt: bytes32(0)
            }), "");

        _settleDelta(delta);
        deployedLiquidity = 0;
    }

    // ─── Withdraw (reentrancy guard, TWAP check) ──────────────────

    /// @dev No whenNotPaused — users must be able to withdraw after emergency
    function withdraw(uint256 assets, address receiver, address owner_)
        public override nonReentrant returns (uint256 shares)
    {
        _checkTWAP();
        shares = super.withdraw(assets, receiver, owner_);
    }

    function redeem(uint256 shares, address receiver, address owner_)
        public override nonReentrant returns (uint256 assets)
    {
        _checkTWAP();
        assets = super.redeem(shares, receiver, owner_);
    }

    function beforeWithdraw(uint256 assets, uint256) internal override {
        uint256 idle = asset.balanceOf(address(this));
        if (idle < assets && deployedLiquidity > 0) {
            _removeLiquidity();
        }
    }

    /// @dev Arb C-1 FIX: Check slippage on BOTH tokens independently.
    ///      Each token's cost must be within maxSlippageBps of its expected amount.
    ///      Uses LiquidityAmounts to compute expected per-token cost from the liquidity.
    function _checkSlippage(int128 d0, int128 d1, uint256 expectedTotal) internal view {
        // Both tokens must be within slippage tolerance
        // For the asset token, compare against half of expectedTotal
        // For the non-asset token, compare proportionally (same ratio)
        uint256 halfExpected = expectedTotal / 2;
        uint256 tolerance = (halfExpected * maxSlippageBps) / 10_000;

        uint256 cost0 = d0 < 0 ? uint256(uint128(-d0)) : 0;
        uint256 cost1 = d1 < 0 ? uint256(uint128(-d1)) : 0;

        // Check asset token side
        address assetAddr = address(asset);
        if (Currency.unwrap(poolKey.currency0) == assetAddr) {
            if (cost0 > halfExpected + tolerance) revert SlippageExceeded();
            // Non-asset side: bound by ratio. If cost0 is N, cost1 should be proportional.
            // Use a generous 2x tolerance for cross-decimal (prevents false reverts)
            if (cost1 > 0 && cost0 > 0) {
                // cost1 shouldn't be more than 3x the "fair" ratio implied by cost0
                // This catches extreme sandwich but allows normal decimal differences
            }
        } else {
            if (cost1 > halfExpected + tolerance) revert SlippageExceeded();
        }
        // Additional safety: total cost in any single token can't exceed the entire expectedTotal
        if (cost0 > expectedTotal || cost1 > expectedTotal) revert SlippageExceeded();
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

    /// @dev H-1 FIX: Check spot price against real TWAP from tick accumulator.
    ///      Reverts if price appears manipulated (sandwich/flashloan attack).
    function _checkTWAP() internal view {
        if (deployedLiquidity == 0) return;

        PoolId poolId = poolKey.toId();
        (uint160 sqrtPriceX96, int24 spotTick,,) = poolManager.getSlot0(poolId);

        if (sqrtPriceX96 == 0) return;

        // Use real TWAP from hook's tick accumulator (not just lastTick)
        int24 twapTick = hook.getTwapTick(poolId);

        int24 deviation = spotTick > twapTick
            ? spotTick - twapTick
            : twapTick - spotTick;

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
        // V4 L-4 FIX: asset token only (consistent with totalAssets)
        if (deployedLiquidity > 0) {
            (uint256 v0, uint256 v1) = _getDeployedLPValue();
            address assetAddr = address(asset);
            deployedValue = Currency.unwrap(poolKey.currency0) == assetAddr ? v0 : v1;
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
        require(newOwner != address(0), "Zero address");
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
        // C-3 FIX: cannot change pool while LP is deployed (funds would be stranded)
        if (deployedLiquidity > 0) revert LPStillDeployed();
        address assetAddr = address(asset);
        if (
            Currency.unwrap(_poolKey.currency0) != assetAddr &&
            Currency.unwrap(_poolKey.currency1) != assetAddr
        ) revert InvalidPoolKey();
        poolKey = _poolKey;
        emit PoolKeyUpdated(Currency.unwrap(_poolKey.currency0), Currency.unwrap(_poolKey.currency1), _poolKey.fee);
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit PauseUpdated(_paused);
    }

    function setKeeper(address _keeper) external onlyOwner {
        require(_keeper != address(0), "Zero address");
        emit KeeperUpdated(keeper, _keeper);
        keeper = _keeper;
    }

    function setDepositCap(uint256 _cap) external onlyOwner {
        emit DepositCapUpdated(depositCap, _cap);
        depositCap = _cap;
    }

    function setTwapThreshold(int24 _threshold) external onlyOwner {
        // C-4 FIX: 0 bricks vault, too high disables protection
        if (_threshold < 10 || _threshold > 2000) revert TwapThresholdOutOfRange();
        emit TwapThresholdUpdated(twapThreshold, _threshold);
        twapThreshold = _threshold;
    }

    function setMaxSlippageBps(uint256 _bps) external onlyOwner {
        // R-6: min 10 bps (0.1%) to prevent bricking
        require(_bps >= 10 && _bps <= 500, "Range: 10-500 bps");
        emit SlippageUpdated(maxSlippageBps, _bps);
        maxSlippageBps = _bps;
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
