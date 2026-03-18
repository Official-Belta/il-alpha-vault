// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/// @title HookMiner
/// @notice Mines CREATE2 salts to find hook addresses with required permission flags.
///         V4 hooks encode permissions in the lowest 14 bits of the deployed address.
library HookMiner {
    /// @notice Find a salt that produces a CREATE2 address with the desired flags
    /// @param deployer The address that will deploy the hook (CREATE2 sender)
    /// @param flags The required permission flags (lower 14 bits of target address)
    /// @param creationCode The contract creation code (type(Hook).creationCode)
    /// @param constructorArgs The ABI-encoded constructor arguments
    /// @return salt The salt that produces a valid address
    /// @return hookAddress The resulting hook address
    function find(
        address deployer,
        uint160 flags,
        bytes memory creationCode,
        bytes memory constructorArgs
    ) internal pure returns (bytes32 salt, address hookAddress) {
        bytes memory initCode = abi.encodePacked(creationCode, constructorArgs);
        bytes32 initCodeHash = keccak256(initCode);

        uint160 flagMask = uint160((1 << 14) - 1); // lower 14 bits

        for (uint256 i = 0; i < 100_000; i++) {
            salt = bytes32(i);
            hookAddress = computeAddress(deployer, salt, initCodeHash);

            if (uint160(hookAddress) & flagMask == flags) {
                return (salt, hookAddress);
            }
        }

        revert("HookMiner: no valid salt found in 100K iterations");
    }

    /// @notice Compute CREATE2 address
    function computeAddress(address deployer, bytes32 salt, bytes32 initCodeHash)
        internal
        pure
        returns (address)
    {
        return address(uint160(uint256(keccak256(abi.encodePacked(bytes1(0xff), deployer, salt, initCodeHash)))));
    }
}
