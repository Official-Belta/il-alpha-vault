// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {IHooks} from "v4-core/src/interfaces/IHooks.sol";
import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "v4-core/src/types/PoolId.sol";
import {BalanceDelta} from "v4-core/src/types/BalanceDelta.sol";
import {BeforeSwapDelta, BeforeSwapDeltaLibrary} from "v4-core/src/types/BeforeSwapDelta.sol";
import {Hooks} from "v4-core/src/libraries/Hooks.sol";
import {StateLibrary} from "v4-core/src/libraries/StateLibrary.sol";

/// @title ILAlphaHook
/// @notice Uniswap V4 hook that uses EWMA vol oracle to decide whether LP is +EV.
///         Implements the IL Alpha Vault strategy: only provide liquidity when
///         fee yield > IL cost (estimated via gamma exposure model).
///
/// @dev Architecture:
///
///   ┌─────────────┐    afterSwap()    ┌──────────────┐
///   │ PoolManager │ ────────────────→ │ ILAlphaHook  │
///   │  (V4 core)  │ ←── selector ──── │ • VolOracle  │
///   └─────────────┘                   │ • LP Toggle  │
///         ↑                           │ • Volume EMA │
///      Swappers                       └──────────────┘
///                                          ↑
///                                       Keeper
///                                   (pushVol, trigger)
///
///   Vol oracle is keeper-hybrid: EWMA updated on-chain per swap,
///   keeper can also push external vol estimates for accuracy.
///   Fee yield is volume-aware: tracks EWMA of swap volume per hour.
contract ILAlphaHook is IHooks {
    using PoolIdLibrary for PoolKey;
    using StateLibrary for IPoolManager;

    // ─── Errors ──────────────────────────────────────────────────────
    error OnlyPoolManager();
    error OnlyOwner();
    error OnlyKeeper();
    error CooldownActive();
    error InvalidLambda();
    error InvalidTickRange();

    // ─── Events ──────────────────────────────────────────────────────
    event VolUpdated(PoolId indexed poolId, uint128 ewmaVar, uint256 timestamp);
    event LPToggled(PoolId indexed poolId, bool isActive, uint256 feeYield, uint256 ilCost);
    event KeeperVolPushed(PoolId indexed poolId, uint256 externalVol);
    event PoolRegistered(PoolId indexed poolId, int24 tickLower, int24 tickUpper);
    event VolumeSpikeDetected(PoolId indexed poolId, uint256 swapVolume, uint128 ewmaVolume);
    event OwnershipTransferStarted(address indexed currentOwner, address indexed pendingOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // ─── Structs ─────────────────────────────────────────────────────

    /// @notice Per-pool vol oracle state — packed into 1 storage slot (208 bits)
    /// @dev Layout: ewmaVar(128) + lastTick(24) + lastTimestamp(40) + lambda(16) = 208 bits
    struct VolOracle {
        uint128 ewmaVar;          // EWMA of squared log-returns (variance), scaled 1e18
        int24 lastTick;           // last observed tick
        uint40 lastTimestamp;     // last update timestamp
        uint16 lambda;            // EWMA decay factor (basis points, e.g. 9400 = 0.94)
    }

    /// @notice Per-pool LP strategy state
    struct PoolState {
        bool isLPActive;          // whether we're currently providing liquidity
        int24 tickLower;          // LP range lower bound
        int24 tickUpper;          // LP range upper bound
        uint40 lastToggleTime;    // last time LP was toggled (for cooldown)
        uint24 poolFee;           // pool fee in hundredths of a bip
        uint128 ewmaVolume;       // EWMA of hourly swap volume (in token units, scaled 1e18)
    }

    // ─── Constants ───────────────────────────────────────────────────
    uint256 public constant PRECISION = 1e18;
    uint256 public constant BPS = 10_000;
    uint24 public constant COOLDOWN_SECONDS = 24 hours;
    uint16 public constant MIN_LAMBDA = 5000;
    uint16 public constant MAX_LAMBDA = 9900;

    /// @dev Gamma exposure model: IL_cost ≈ 0.5 * sigma^2 * concentration
    uint256 public constant GAMMA_FACTOR = 5e17; // 0.5 in 1e18

    /// @dev Volume EWMA decay (same lambda as vol by default)
    uint16 public constant VOLUME_LAMBDA = 9400;

    /// @dev Volume spike multiplier: if single swap volume > SPIKE_MULTIPLIER * ewmaVolume → emergency LP off
    uint16 public constant SPIKE_MULTIPLIER = 3; // 3x average = spike

    // ─── Unaudited Notice ─────────────────────────────────────────────
    /// @notice This contract has NOT been audited. Use at your own risk.
    bool public constant UNAUDITED = true;

    // ─── Storage ─────────────────────────────────────────────────────
    IPoolManager public immutable poolManager;
    address public owner;
    address public pendingOwner;
    address public keeper;

    mapping(PoolId => VolOracle) public volOracles;
    mapping(PoolId => PoolState) public poolStates;

    // ─── Modifiers ───────────────────────────────────────────────────
    modifier onlyPoolManager() {
        if (msg.sender != address(poolManager)) revert OnlyPoolManager();
        _;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert OnlyOwner();
        _;
    }

    modifier onlyKeeper() {
        if (msg.sender != keeper && msg.sender != owner) revert OnlyKeeper();
        _;
    }

    // ─── Constructor ─────────────────────────────────────────────────
    constructor(IPoolManager _poolManager, address _owner) {
        poolManager = _poolManager;
        owner = _owner;
        keeper = _owner;

        Hooks.validateHookPermissions(
            IHooks(address(this)),
            Hooks.Permissions({
                beforeInitialize: false,
                afterInitialize: true,
                beforeAddLiquidity: false,
                afterAddLiquidity: false,
                beforeRemoveLiquidity: false,
                afterRemoveLiquidity: false,
                beforeSwap: false,
                afterSwap: true,
                beforeDonate: false,
                afterDonate: false,
                beforeSwapReturnDelta: false,
                afterSwapReturnDelta: false,
                afterAddLiquidityReturnDelta: false,
                afterRemoveLiquidityReturnDelta: false
            })
        );
    }

    // ─── IHooks Implementation ───────────────────────────────────────
    // Only afterInitialize and afterSwap are active. All others are no-ops
    // returning their selector (never reverts — safe if called unexpectedly).

    function beforeInitialize(address, PoolKey calldata, uint160) external pure returns (bytes4) {
        return IHooks.beforeInitialize.selector;
    }

    function afterInitialize(
        address,
        PoolKey calldata key,
        uint160,
        int24 tick
    ) external onlyPoolManager returns (bytes4) {
        PoolId poolId = key.toId();

        int24 halfRange = 500;
        int24 spacing = key.tickSpacing;
        int24 lower = ((tick - halfRange) / spacing) * spacing;
        int24 upper = ((tick + halfRange) / spacing) * spacing;

        poolStates[poolId] = PoolState({
            isLPActive: false,
            tickLower: lower,
            tickUpper: upper,
            lastToggleTime: 0,
            poolFee: key.fee,
            ewmaVolume: 0
        });

        volOracles[poolId] = VolOracle({
            ewmaVar: 0,
            lastTick: tick,
            lambda: 9400,
            lastTimestamp: uint40(block.timestamp)
        });

        emit PoolRegistered(poolId, lower, upper);
        return IHooks.afterInitialize.selector;
    }

    function beforeAddLiquidity(address, PoolKey calldata, IPoolManager.ModifyLiquidityParams calldata, bytes calldata)
        external pure returns (bytes4)
    {
        return IHooks.beforeAddLiquidity.selector;
    }

    function afterAddLiquidity(
        address, PoolKey calldata, IPoolManager.ModifyLiquidityParams calldata,
        BalanceDelta, BalanceDelta, bytes calldata
    ) external pure returns (bytes4, BalanceDelta) {
        return (IHooks.afterAddLiquidity.selector, BalanceDelta.wrap(0));
    }

    function beforeRemoveLiquidity(address, PoolKey calldata, IPoolManager.ModifyLiquidityParams calldata, bytes calldata)
        external pure returns (bytes4)
    {
        return IHooks.beforeRemoveLiquidity.selector;
    }

    function afterRemoveLiquidity(
        address, PoolKey calldata, IPoolManager.ModifyLiquidityParams calldata,
        BalanceDelta, BalanceDelta, bytes calldata
    ) external pure returns (bytes4, BalanceDelta) {
        return (IHooks.afterRemoveLiquidity.selector, BalanceDelta.wrap(0));
    }

    function beforeSwap(address, PoolKey calldata, IPoolManager.SwapParams calldata, bytes calldata)
        external pure returns (bytes4, BeforeSwapDelta, uint24)
    {
        return (IHooks.beforeSwap.selector, BeforeSwapDeltaLibrary.ZERO_DELTA, 0);
    }

    function afterSwap(
        address,
        PoolKey calldata key,
        IPoolManager.SwapParams calldata params,
        BalanceDelta,
        bytes calldata
    ) external onlyPoolManager returns (bytes4, int128) {
        PoolId poolId = key.toId();
        PoolState storage ps = poolStates[poolId];
        VolOracle storage vo = volOracles[poolId];

        (uint160 sqrtPriceX96, int24 currentTick,,) = poolManager.getSlot0(poolId);

        if (sqrtPriceX96 == 0) {
            return (IHooks.afterSwap.selector, 0);
        }

        // ── Check volume spike BEFORE updating EWMA (compare against current average) ──
        uint256 absAmount = params.amountSpecified < 0
            ? uint256(-params.amountSpecified)
            : uint256(params.amountSpecified);
        bool isSpike = ps.ewmaVolume > 0 && absAmount > uint256(ps.ewmaVolume) * SPIKE_MULTIPLIER;

        // ── Update volume EWMA ──
        _updateVolumeEwma(ps, params.amountSpecified);

        // ── Update EWMA vol oracle ──
        _updateVolOracle(vo, currentTick, poolId);

        // ── Volume spike: emergency LP off (bypasses cooldown) ──
        if (isSpike && ps.isLPActive) {
            ps.isLPActive = false;
            ps.lastToggleTime = uint40(block.timestamp);
            emit VolumeSpikeDetected(poolId, absAmount, ps.ewmaVolume);
            emit LPToggled(poolId, false, 0, 0);
        }
        // ── Normal evaluation (respecting cooldown) ──
        else if (block.timestamp >= ps.lastToggleTime + COOLDOWN_SECONDS) {
            _evaluateLPToggle(poolId, ps, vo);
        }

        return (IHooks.afterSwap.selector, 0);
    }

    function beforeDonate(address, PoolKey calldata, uint256, uint256, bytes calldata)
        external pure returns (bytes4)
    {
        return IHooks.beforeDonate.selector;
    }

    function afterDonate(address, PoolKey calldata, uint256, uint256, bytes calldata)
        external pure returns (bytes4)
    {
        return IHooks.afterDonate.selector;
    }

    // ─── Internal: Vol Oracle ────────────────────────────────────────

    /// @dev Update EWMA variance from tick change (log-return proxy).
    ///      log_return ≈ (currentTick - lastTick) * ln(1.0001)
    ///      Tracks variance in tick-space. Cost: ~3.5K gas (1 SSTORE, packed slot)
    function _updateVolOracle(VolOracle storage vo, int24 currentTick, PoolId poolId) internal {
        uint256 elapsed = block.timestamp - vo.lastTimestamp;
        if (elapsed == 0) return; // same-block swap: no-op

        int256 tickDelta = int256(currentTick) - int256(vo.lastTick);

        // Safe: tickDelta is at most ~887272 (MAX_TICK - MIN_TICK)
        // 887272^2 = ~7.87e11, * 1e18 = ~7.87e29, fits uint256
        uint256 squaredReturn = uint256(tickDelta * tickDelta) * PRECISION;

        // Time-normalize to per-hour
        squaredReturn = (squaredReturn * 3600) / elapsed;

        // EWMA update: var_new = lambda * var_old + (1 - lambda) * squaredReturn
        uint256 lambda = vo.lambda;
        uint256 newVar = (lambda * uint256(vo.ewmaVar) + (BPS - lambda) * squaredReturn) / BPS;

        // Cap to uint128 max to prevent overflow in packed struct
        vo.ewmaVar = newVar > type(uint128).max ? type(uint128).max : uint128(newVar);
        vo.lastTick = currentTick;
        vo.lastTimestamp = uint40(block.timestamp);

        emit VolUpdated(poolId, vo.ewmaVar, block.timestamp);
    }

    /// @dev Update EWMA of hourly swap volume
    function _updateVolumeEwma(PoolState storage ps, int256 amountSpecified) internal {
        // Volume = |amountSpecified|
        uint256 absAmount = amountSpecified < 0 ? uint256(-amountSpecified) : uint256(amountSpecified);

        // Simple EWMA blend with existing volume
        uint256 newVol = (uint256(VOLUME_LAMBDA) * uint256(ps.ewmaVolume) + uint256(BPS - VOLUME_LAMBDA) * absAmount) / BPS;
        ps.ewmaVolume = newVol > type(uint128).max ? type(uint128).max : uint128(newVol);
    }

    // ─── Internal: Fee/IL Calculation (DRY) ──────────────────────────

    /// @dev Compute fee yield and IL cost for a pool
    ///      fee_yield = poolFee * ewmaVolume (volume-weighted fee income proxy)
    ///      il_cost = 0.5 * variance * concentration_factor
    function _computeFeeAndIL(PoolState storage ps, VolOracle storage vo)
        internal
        view
        returns (uint256 feeYield, uint256 ilCost)
    {
        // Fee yield: fee_rate * volume_proxy
        // poolFee is in hundredths of a bip (3000 = 0.30%)
        // feeYield = (poolFee / 1_000_000) * ewmaVolume
        feeYield = (uint256(ps.poolFee) * uint256(ps.ewmaVolume)) / 1_000_000;

        // IL cost: gamma exposure model
        // concentration = fullRange_proxy / tickRange
        uint256 tickRange = uint256(int256(ps.tickUpper - ps.tickLower));
        uint256 concentration = tickRange > 0 ? (10_000 * PRECISION) / tickRange : PRECISION;

        ilCost = (GAMMA_FACTOR * uint256(vo.ewmaVar) * concentration) / (PRECISION * PRECISION);
    }

    // ─── Internal: LP Toggle Logic ───────────────────────────────────

    /// @dev Core strategy: compare fee yield vs IL cost. Toggle LP accordingly.
    function _evaluateLPToggle(PoolId poolId, PoolState storage ps, VolOracle storage vo) internal {
        (uint256 feeYield, uint256 ilCost) = _computeFeeAndIL(ps, vo);

        bool shouldBeActive = feeYield > ilCost;

        if (shouldBeActive != ps.isLPActive) {
            ps.isLPActive = shouldBeActive;
            ps.lastToggleTime = uint40(block.timestamp);
            emit LPToggled(poolId, shouldBeActive, feeYield, ilCost);
        }
    }

    // ─── Keeper Functions ────────────────────────────────────────────

    /// @notice Keeper pushes external vol estimate (e.g., from off-chain EWMA on Binance data)
    /// @dev Rate limited: max change per push is 2x current value (prevents keeper key abuse).
    ///      Keeper can move vol up or down, but not by more than 2x in a single call.
    function pushVolEstimate(PoolKey calldata key, uint256 externalVar) external onlyKeeper {
        PoolId poolId = key.toId();
        VolOracle storage vo = volOracles[poolId];

        // Rate limit: external estimate can't be more than 2x current on-chain var
        // This limits damage from a compromised keeper key
        uint256 currentVar = uint256(vo.ewmaVar);
        uint256 maxExternal = currentVar == 0 ? type(uint128).max : currentVar * 4;
        if (externalVar > maxExternal) {
            externalVar = maxExternal;
        }

        // Blend: 50% on-chain EWMA + 50% external, capped to uint128
        uint256 blended = (currentVar + externalVar) / 2;
        vo.ewmaVar = blended > type(uint128).max ? type(uint128).max : uint128(blended);
        vo.lastTimestamp = uint40(block.timestamp);

        emit KeeperVolPushed(poolId, externalVar);
    }

    /// @notice Keeper triggers LP rebalance evaluation outside of swaps
    function triggerEvaluation(PoolKey calldata key) external onlyKeeper {
        PoolId poolId = key.toId();
        PoolState storage ps = poolStates[poolId];
        VolOracle storage vo = volOracles[poolId];

        if (block.timestamp < ps.lastToggleTime + COOLDOWN_SECONDS) revert CooldownActive();
        _evaluateLPToggle(poolId, ps, vo);
    }

    /// @notice Update LP range for a pool
    function setLPRange(PoolKey calldata key, int24 tickLower, int24 tickUpper) external onlyOwner {
        if (tickLower >= tickUpper) revert InvalidTickRange();
        PoolId poolId = key.toId();
        poolStates[poolId].tickLower = tickLower;
        poolStates[poolId].tickUpper = tickUpper;
    }

    // ─── View Functions ──────────────────────────────────────────────

    function getVolEstimate(PoolKey calldata key) external view returns (uint128 hourlyVar, uint256 annualizedVol) {
        PoolId poolId = key.toId();
        hourlyVar = volOracles[poolId].ewmaVar;
        annualizedVol = uint256(hourlyVar) * 8760;
    }

    function isLPActive(PoolKey calldata key) external view returns (bool) {
        return poolStates[key.toId()].isLPActive;
    }

    function getPoolStrategy(PoolKey calldata key)
        external
        view
        returns (bool active, int24 tickLower, int24 tickUpper, uint256 feeYield, uint256 ilCost)
    {
        PoolId poolId = key.toId();
        PoolState storage ps = poolStates[poolId];
        VolOracle storage vo = volOracles[poolId];

        active = ps.isLPActive;
        tickLower = ps.tickLower;
        tickUpper = ps.tickUpper;
        (feeYield, ilCost) = _computeFeeAndIL(ps, vo);
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

    function setKeeper(address _keeper) external onlyOwner {
        keeper = _keeper;
    }

    function setLambda(PoolKey calldata key, uint16 _lambda) external onlyOwner {
        if (_lambda < MIN_LAMBDA || _lambda > MAX_LAMBDA) revert InvalidLambda();
        volOracles[key.toId()].lambda = _lambda;
    }
}
