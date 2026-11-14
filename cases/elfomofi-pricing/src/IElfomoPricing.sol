// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;


interface IElfomoPricing {

    struct TokenPair {
        address tokenA;
        address tokenB;
    }
    
    function getAmountOut(
        address fromToken,
        address toToken,
        uint256 fromAmount,
        address executor,
        uint256 partnerId
    ) external view returns (uint256 toAmount, uint256 quoteId, bytes memory data);

    function getAmountIn(
        address fromToken,
        address toToken,
        uint256 toAmount,
        address executor,
        uint256 partnerId
    ) external view returns (uint256 fromAmount, uint256 quoteId, bytes memory data);

    function update(
        uint256 quoteId,
        bytes memory data,
        address fromToken,
        address toToken,
        uint256 fromAmount,
        uint256 toAmount,
        address executor,
        uint256 partnerId
    ) external;

    function getSupportedPairs() external view returns (TokenPair[] memory);

}