// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {IPoolManager} from "v4-core/src/interfaces/IPoolManager.sol";
import {IUnlockCallback} from "v4-core/src/interfaces/callback/IUnlockCallback.sol";
import {PoolKey} from "v4-core/src/types/PoolKey.sol";
import {Currency} from "v4-core/src/types/Currency.sol";
import {BalanceDelta} from "v4-core/src/types/BalanceDelta.sol";
import {TickMath} from "v4-core/src/libraries/TickMath.sol";
import {ERC20} from "solmate/src/tokens/ERC20.sol";
import {SafeTransferLib} from "solmate/src/utils/SafeTransferLib.sol";

/// @title SwapHelper
/// @notice Helper for keeper bot to execute swaps and add liquidity on testnet.
///         Generates volume in the pool so afterSwap hook fires and ewmaVolume updates.
contract SwapHelper is IUnlockCallback {
    using SafeTransferLib for ERC20;

    IPoolManager public immutable poolManager;
    address public owner;
    bool private _locked;

    PoolKey private _pendingKey;
    bool private _pendingZeroForOne;
    int256 private _pendingAmount;
    bool private _isSwap; // true = swap, false = addLiquidity

    error OnlyOwner();
    error OnlyPoolManager();

    constructor(IPoolManager _poolManager) {
        poolManager = _poolManager;
        owner = msg.sender;
    }

    /// @notice Execute a swap. Caller must have approved tokens to this contract.
    function swap(PoolKey calldata key, bool zeroForOne, int256 amountSpecified) external {
        if (msg.sender != owner) revert OnlyOwner();
        require(!_locked, "Reentrancy");
        _locked = true;

        _pendingKey = key;
        _pendingZeroForOne = zeroForOne;
        _pendingAmount = amountSpecified;
        _isSwap = true;

        poolManager.unlock(abi.encode(msg.sender));
        _locked = false;
    }

    /// @notice Add liquidity to the pool. Caller must have approved tokens.
    function addLiquidity(PoolKey calldata key, int256 liquidityDelta) external {
        if (msg.sender != owner) revert OnlyOwner();
        require(!_locked, "Reentrancy");
        _locked = true;

        _pendingKey = key;
        _pendingAmount = liquidityDelta;
        _isSwap = false;

        poolManager.unlock(abi.encode(msg.sender));
        _locked = false;
    }

    function unlockCallback(bytes calldata data) external returns (bytes memory) {
        if (msg.sender != address(poolManager)) revert OnlyPoolManager();

        address caller = abi.decode(data, (address));

        if (!_isSwap) {
            return _executeAddLiquidity(caller);
        }

        IPoolManager.SwapParams memory params = IPoolManager.SwapParams({
            zeroForOne: _pendingZeroForOne,
            amountSpecified: _pendingAmount,
            sqrtPriceLimitX96: _pendingZeroForOne
                ? TickMath.MIN_SQRT_PRICE + 1
                : TickMath.MAX_SQRT_PRICE - 1
        });

        BalanceDelta delta = poolManager.swap(_pendingKey, params, "");

        // Settle negative deltas (we owe tokens)
        int128 d0 = delta.amount0();
        int128 d1 = delta.amount1();

        if (d0 < 0) {
            Currency c = _pendingKey.currency0;
            uint256 amt = uint256(uint128(-d0));
            poolManager.sync(c);
            ERC20(Currency.unwrap(c)).safeTransferFrom(caller, address(poolManager), amt);
            poolManager.settle();
        }
        if (d1 < 0) {
            Currency c = _pendingKey.currency1;
            uint256 amt = uint256(uint128(-d1));
            poolManager.sync(c);
            ERC20(Currency.unwrap(c)).safeTransferFrom(caller, address(poolManager), amt);
            poolManager.settle();
        }

        // Take positive deltas (pool owes us tokens → send to caller)
        if (d0 > 0) poolManager.take(_pendingKey.currency0, caller, uint256(uint128(d0)));
        if (d1 > 0) poolManager.take(_pendingKey.currency1, caller, uint256(uint128(d1)));

        return "";
    }

    function _executeAddLiquidity(address caller) internal returns (bytes memory) {
        IPoolManager.ModifyLiquidityParams memory params = IPoolManager.ModifyLiquidityParams({
            tickLower: -887220,
            tickUpper: 887220,
            liquidityDelta: _pendingAmount,
            salt: bytes32(0)
        });

        (BalanceDelta delta,) = poolManager.modifyLiquidity(_pendingKey, params, "");

        int128 d0 = delta.amount0();
        int128 d1 = delta.amount1();

        if (d0 < 0) {
            Currency c = _pendingKey.currency0;
            uint256 amt = uint256(uint128(-d0));
            poolManager.sync(c);
            ERC20(Currency.unwrap(c)).safeTransferFrom(caller, address(poolManager), amt);
            poolManager.settle();
        }
        if (d1 < 0) {
            Currency c = _pendingKey.currency1;
            uint256 amt = uint256(uint128(-d1));
            poolManager.sync(c);
            ERC20(Currency.unwrap(c)).safeTransferFrom(caller, address(poolManager), amt);
            poolManager.settle();
        }

        if (d0 > 0) poolManager.take(_pendingKey.currency0, caller, uint256(uint128(d0)));
        if (d1 > 0) poolManager.take(_pendingKey.currency1, caller, uint256(uint128(d1)));

        return "";
    }
}
