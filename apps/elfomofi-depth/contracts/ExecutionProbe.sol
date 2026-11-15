// SPDX-License-Identifier: MIT
pragma solidity 0.8.34;

interface Engine {
    function getAmountOut(address,address,uint256,address,uint256) external view returns(uint256,uint256,bytes memory);
    function getAmountIn(address,address,uint256,address,uint256) external view returns(uint256,uint256,bytes memory);
    function update(uint256,bytes memory,address,address,uint256,uint256,address,uint256) external;
}

/// Research instrumentation installed at the pricing proxy only inside eth_call.
/// Never deployed. Original engine, helper, oracle and token code are preserved.
contract ExecutionProbe {
    address constant ENGINE = 0x84cB1a96E57E9b88cF75035384c06DC3769654AE;
    address constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;

    // 0: quote + update passed, 1: no quote, 2: quote reverted, 3: update reverted.
    function simulate(address token, uint256 amount, bool buy, uint8 callerClass, address executor, bool warmRoute)
        external returns(uint256 quote, uint256 quoteId, uint256 status, bytes memory reason, uint256 gasUsed, uint256 warmCodeSize)
    {
        require(callerClass <= 43 && amount > 0, "scenario");
        assembly { tstore(0x9a8254eab367d08c, callerClass) }
        if (warmRoute) warmCodeSize = address(0x9008D19f58AAbD9eD0D60971565AA8510560ab41).code.length;
        address from = buy ? USDC : token;
        address to = buy ? token : USDC;
        bytes memory input = abi.encodeWithSelector(buy ? Engine.getAmountIn.selector : Engine.getAmountOut.selector, from, to, amount, executor, 0);
        uint256 initialGas = gasleft();
        (bool ok, bytes memory result) = ENGINE.staticcall(input);
        if (!ok) return (0,0,2,result,initialGas-gasleft(),warmCodeSize);
        (quote,quoteId,) = abi.decode(result,(uint256,uint256,bytes));
        if (quote == 0) return (quote,quoteId,1,"",initialGas-gasleft(),warmCodeSize);
        // An independent fill: no transfers, allowances, balances or future state are fabricated.
        (ok,reason) = ENGINE.call(abi.encodeWithSelector(Engine.update.selector,quoteId,bytes(""),from,to,buy?quote:amount,buy?amount:quote,executor,0));
        return (quote,quoteId,ok?0:3,reason,initialGas-gasleft(),warmCodeSize);
    }

    fallback() external {
        require(msg.sender == ENGINE && msg.sig == bytes4(0x725e6ced), "classifier");
        assembly { mstore(0,tload(0x9a8254eab367d08c)) return(0,32) }
    }
}
