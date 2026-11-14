// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";

interface ICurveUint {
    function exchange(uint256 i, uint256 j, uint256 dx, uint256 minDy) external;
}
interface ICurveInt {
    function exchange(int128 i, int128 j, uint256 dx, uint256 minDy) external;
}
interface ICurveReturn {
    function exchange(int128 i, int128 j, uint256 dx, uint256 minDy) external payable returns (uint256);
}
interface IBalancerV1 {
    function swapExactAmountIn(address tokenIn, uint256 amountIn, address tokenOut, uint256 minOut, uint256 maxPrice)
        external returns (uint256 amountOut, uint256 spotPriceAfter);
}
interface IBalancerPool {
    function getPoolId() external view returns (bytes32);
}
interface IAsset {}
interface IBalancerVault {
    enum SwapKind { GIVEN_IN, GIVEN_OUT }
    enum PoolSpecialization { GENERAL, MINIMAL_SWAP_INFO, TWO_TOKEN }
    struct SingleSwap { bytes32 poolId; SwapKind kind; IAsset assetIn; IAsset assetOut; uint256 amount; bytes userData; }
    struct FundManagement { address sender; bool fromInternalBalance; address payable recipient; bool toInternalBalance; }
    function swap(SingleSwap memory singleSwap, FundManagement memory funds, uint256 limit, uint256 deadline)
        external payable returns (uint256);
    function getPool(bytes32 id) external view returns (address, uint8);
}

/// @notice Independently reconstructed from the Ethereum runtime at
/// 0xec6fc9be2d5e505b40a2df8b0622cd25333823db. This is not an official Wintermute release.
/// @dev Recovered function names are selected to preserve the original selectors;
/// parameter names and event names are explanatory. Low-level return checks are
/// intentionally preserved rather than strengthened.
contract Executor {
    using SafeERC20 for IERC20;
    using EnumerableSet for EnumerableSet.AddressSet;

    struct Approval { address spender; address token; uint256 amount; }

    bytes32 public constant operatorRole = 0x50bd042dce90a5f0c1e33b44d95fd2c944e96f9d6be45bffae0d6c77ec711f4a;
    bytes32 public constant recovered_jpbl5r800000 = 0x54823ecad1e5445a9de111f3d8b0c63e51c0fc62cbe5692cb23e4e6da2250cbf; // Curve pool role
    bytes32 public constant coinbaseAddressRole = 0xcd5e156b3b60ca632455aa361bb28c1ad131c0050790057278c334308b9eae2a;
    bytes32 public constant approvedSpenderRole = 0x8a86140c2df97ed57d0d23317d04e2381eaf3b7477eb2c24abd4c921f473bfca;
    bytes32 public constant recovered_i49mj1d00000 = 0x202f55c021fba7fb6834611facfd6443d7b984ab0b2a7985e89ad5e1dc96b0af; // Balancer V1 role
    bytes32 public constant recovered_ftdj1u300000 = 0x47ae38ccf90de8127449ca7ff05a9f876fb5c58a389e7bd013f98540dbde7b76; // Balancer V2 role

    address public immutable multiSigOwner;
    address public immutable accessControlRegistry;
    address public immutable contractWallet;
    address public immutable WETHAddress;
    address public immutable balancerVaultAddress;
    IBalancerVault internal immutable balancerVault;
    uint256 internal immutable timelockDelay;

    bool public isActive = true;
    mapping(address => bool) public _operators;
    mapping(address => bool) public _approvedCoinbaseAddresses;
    mapping(address => bool) public recovered_fhqu41500000; // approved Curve pools
    mapping(address => bool) public recovered_19b9lm300000; // approved Balancer V1 pools
    mapping(bytes32 => bool) public recovered_jnq35c100000; // approved Balancer V2 pool IDs
    EnumerableSet.AddressSet internal _approvedSpenders;
    EnumerableSet.AddressSet internal _approvedTokens;

    bytes32 private constant EV_APPROVED = 0x078feb5c78145a99888e920c37992a7c5f29afd100968c2b1daae0dd1c13735c;
    bytes32 private constant EV_REVOKED = 0x2fd789bdca46f7a5ffb87d24710236a348b3db6302b634fed17afef685cd119f;
    bytes32 private constant EV_FAILURE = 0x1dc40890bf891c9fa3478feee4d91fd3439ea18850bb7864aa2838a51e73a7e6;
    event TokensApproved(bytes32 indexed topic) anonymous;
    event ApprovalsRevoked(bytes32 indexed topic) anonymous;
    event ApprovalRevokeFailed(bytes32 indexed topic, address token, address spender) anonymous;

    constructor(address owner, address registry, address wallet, uint256 delay, address weth, address vault) {
        multiSigOwner = owner;
        accessControlRegistry = registry;
        contractWallet = wallet;
        timelockDelay = delay;
        WETHAddress = weth;
        balancerVaultAddress = vault;
        balancerVault = IBalancerVault(vault);
    }
    modifier whenActive() { require(isActive, "C1"); _; }
    modifier onlyMultiSig() { require(msg.sender == multiSigOwner, "C2"); _; }
    modifier onlyRegistry() { require(msg.sender == accessControlRegistry, "C3"); _; }
    modifier onlyOperator() { require(_operators[msg.sender], "C4"); _; }
    modifier onlyCurvePool(address pool) { require(recovered_fhqu41500000[pool], "C7"); _; }
    modifier onlyBalancerV1Pool(address pool) { require(recovered_19b9lm300000[pool], "C21"); _; }
    modifier onlyBalancerV2Pool(bytes32 poolId) { require(recovered_jnq35c100000[poolId], "C21"); _; }
    modifier ensure(uint256 deadline) { require(deadline >= block.timestamp, "C8"); _; }
    receive() external payable {}
    fallback() external payable {}

    /// @notice Registry callback: grant an operator, pool, coinbase, or spender role.
    /// @custom:original-selector 0xcf1346bc
    function recovered_hhe311200000(bytes32 role, address account, bytes memory data) external onlyRegistry {
        if (role == operatorRole) { _add(_operators, account); }
        else if (role == recovered_jpbl5r800000) { _add(recovered_fhqu41500000, account); }
        else if (role == coinbaseAddressRole) { _add(_approvedCoinbaseAddresses, account); }
        else if (role == approvedSpenderRole) {
            require(!_approvedSpenders.contains(account), "C9");
            _approvedSpenders.add(account);
        } else if (role == recovered_i49mj1d00000) { _add(recovered_19b9lm300000, account); }
        else if (role == recovered_ftdj1u300000) {
            bytes32 id = recovered_g6qibk000000(account);
            require(recovered_312p15600000(id) == account, "C18");
            require(!recovered_jnq35c100000[id], "C19");
            recovered_jnq35c100000[id] = true;
        } else { revert("UNKNOWN ROLE"); }
    }
    /// @notice Registry callback: revoke a role, clearing allowances when removing a spender.
    /// @custom:original-selector 0x59733e7f
    function recovered_b3pefig00000(bytes32 role, address account, bytes memory data) external onlyRegistry {
        if (role == operatorRole) { _remove(_operators, account); }
        else if (role == recovered_jpbl5r800000) { _remove(recovered_fhqu41500000, account); }
        else if (role == coinbaseAddressRole) { _remove(_approvedCoinbaseAddresses, account); }
        else if (role == approvedSpenderRole) {
            require(_approvedSpenders.contains(account), "C10");
            _revokeSpender(account);
        } else if (role == recovered_i49mj1d00000) { _remove(recovered_19b9lm300000, account); }
        else if (role == recovered_ftdj1u300000) {
            bytes32 id = recovered_g6qibk000000(account);
            require(recovered_312p15600000(id) == account, "C18");
            require(recovered_jnq35c100000[id], "C20");
            recovered_jnq35c100000[id] = false;
        } else { revert("UNKNOWN ROLE"); }
    }
    function _add(mapping(address => bool) storage map, address account) internal {
        require(!map[account], "C9"); map[account] = true;
    }
    function _remove(mapping(address => bool) storage map, address account) internal {
        require(map[account], "C10"); map[account] = false;
    }

    function getTimelockDelay() external view returns (uint256) { return timelockDelay; }
    function getAllApprovedSpenders() external view returns (address[] memory) { return _approvedSpenders.values(); }
    function getAllApprovedTokens() external view returns (address[] memory) { return _approvedTokens.values(); }
    function killContract() external {
        require(_operators[msg.sender] || msg.sender == multiSigOwner, "C11");
        isActive = false;
    }
    function unkillContract() external onlyMultiSig { isActive = true; }
    /// @notice Read a Balancer pool ID from its pool contract.
    /// @custom:original-selector 0x19283043
    function recovered_g6qibk000000(address pool) public view returns (bytes32) { return IBalancerPool(pool).getPoolId(); }
    /// @notice Resolve a Balancer pool ID through the immutable vault.
    /// @custom:original-selector 0x534c83e5
    function recovered_312p15600000(bytes32 id) public view returns (address) {
        (address pool,) = balancerVault.getPool(id); return pool;
    }
    /// @notice Owner approval batch; each spender must already be approved.
    /// @custom:original-selector 0x3cbe46f8
    function recovered_53rk7q200000(Approval[] memory approvals) external onlyMultiSig whenActive {
        for (uint256 i = 0; i < approvals.length; i++) {
            IERC20 token = IERC20(approvals[i].token);
            require(_approvedSpenders.contains(approvals[i].spender), "C12");
            token.safeApprove(approvals[i].spender, approvals[i].amount);
            _approvedTokens.add(approvals[i].token);
        }
        emit TokensApproved(EV_APPROVED);
    }
    /// @notice Deactivate execution and revoke approvals for every tracked token.
    /// @custom:original-selector 0xa5fd3043
    function recovered_aa22rp000000() public {
        require(_operators[msg.sender] || msg.sender == multiSigOwner, "C11");
        recovered_jspoj0000000(_approvedTokens.length());
    }
    /// @notice Deactivate execution and remove the requested number of tracked tokens.
    /// @dev Failed low-level allowance/approval calls emit the recovered failure topic.
    /// @custom:original-selector 0xf203c1b1
    function recovered_jspoj0000000(uint256 count) public {
        require(_operators[msg.sender] || msg.sender == multiSigOwner, "C11");
        isActive = false;
        require(count <= _approvedTokens.length(), "C13");
        uint256 i = 0;
        while (i < count) {
            address token = _approvedTokens.at(0);
            i++;
            _approvedTokens.remove(token);
            for (uint256 j = 0; j < _approvedSpenders.length(); j++) {
                address spender = _approvedSpenders.at(j);
                (bool success, bytes memory result) = token.staticcall(abi.encodeWithSelector(IERC20.allowance.selector, address(this), spender));
                uint256 allowance = 0;
                if (!success) { emit ApprovalRevokeFailed(EV_FAILURE, token, spender); }
                else { allowance = abi.decode(result, (uint256)); }
                if (allowance > 0) {
                    (success,) = token.call(abi.encodeWithSelector(IERC20.approve.selector, spender, 0));
                    if (!success) emit ApprovalRevokeFailed(EV_FAILURE, token, spender);
                }
            }
        }
        emit ApprovalsRevoked(EV_REVOKED);
    }
    function _revokeSpender(address spender) internal {
        require(_approvedSpenders.contains(spender), "");
        for (uint256 i = 0; i < _approvedTokens.length(); i++) {
            address token = _approvedTokens.at(i);
            (bool success, bytes memory result) = token.staticcall(abi.encodeWithSelector(IERC20.allowance.selector, address(this), spender));
            uint256 allowance = 0;
            if (!success) { emit ApprovalRevokeFailed(EV_FAILURE, token, spender); }
            else { allowance = abi.decode(result, (uint256)); }
            if (allowance > 0) {
                (success,) = token.call(abi.encodeWithSelector(IERC20.approve.selector, spender, 0));
                if (!success) emit ApprovalRevokeFailed(EV_FAILURE, token, spender);
            }
        }
        _approvedSpenders.remove(spender);
        emit ApprovalsRevoked(EV_REVOKED);
    }
    /// @notice Owner transfer of token amounts to one recipient.
    /// @custom:original-selector 0x2c88026b
    function recovered_3hgj34f00000(address[] memory tokens, uint256[] memory amounts, address to) external onlyMultiSig {
        require(tokens.length == amounts.length, "C15");
        for (uint256 i = 0; i < tokens.length; i++) IERC20(tokens[i]).safeTransfer(to, amounts[i]);
    }
    /// @notice Owner ETH transfer; the low-level call result is deliberately ignored.
    /// @custom:original-selector 0x8f05e71b
    function recovered_gatlfh100000(uint256 amount, address to) external onlyMultiSig { payable(to).call{value: amount}(""); }

    function curveSwap(uint256 tip, address pool, uint256 i, uint256 j, uint256 dx, uint256 minDy, address tokenIn, address tokenOut)
        public payable whenActive onlyCurvePool(pool) onlyOperator {
        tokenIn.call(abi.encodeWithSelector(IERC20.transferFrom.selector, contractWallet, address(this), dx));
        ICurveUint(pool).exchange(i, j, dx, minDy);
        (bool success,) = tokenOut.call(abi.encodeWithSelector(IERC20.transfer.selector, contractWallet, IERC20(tokenOut).balanceOf(address(this))));
        require(success, "C16");
        _tip(tip);
    }
    function curveSwapDL(uint256 tip, address pool, uint256 i, uint256 j, uint256 dx, uint256 minDy, address tokenIn, address tokenOut, uint256 deadline)
        external payable ensure(deadline) { curveSwap(tip, pool, i, j, dx, minDy, tokenIn, tokenOut); }
    function curveSwap3(uint256 tip, address pool, int128 i, int128 j, uint256 dx, uint256 minDy, address tokenIn, address tokenOut)
        public payable whenActive onlyCurvePool(pool) onlyOperator {
        tokenIn.call(abi.encodeWithSelector(IERC20.transferFrom.selector, contractWallet, address(this), dx));
        ICurveInt(pool).exchange(i, j, dx, minDy);
        (bool success,) = tokenOut.call(abi.encodeWithSelector(IERC20.transfer.selector, contractWallet, IERC20(tokenOut).balanceOf(address(this))));
        require(success, "C16");
        _tip(tip);
    }
    function curveSwap3DL(uint256 tip, address pool, int128 i, int128 j, uint256 dx, uint256 minDy, address tokenIn, address tokenOut, uint256 deadline)
        external payable ensure(deadline) { curveSwap3(tip, pool, i, j, dx, minDy, tokenIn, tokenOut); }
    function curveSwap2(uint256 tip, address pool, int128 i, int128 j, uint256 dx, uint256 minDy, bool wrapEth, address tokenIn, address tokenOut)
        public payable whenActive onlyCurvePool(pool) onlyOperator {
        tokenIn.call(abi.encodeWithSelector(IERC20.transferFrom.selector, contractWallet, address(this), dx));
        uint256 dy = ICurveReturn(pool).exchange(i, j, dx, minDy);
        if (!wrapEth) {
            (bool success,) = tokenOut.call(abi.encodeWithSelector(IERC20.transfer.selector, contractWallet, dy));
            require(success, "C16");
        } else {
            WETHAddress.call{value: dy}(abi.encodeWithSignature("deposit()"));
            (bool success,) = WETHAddress.call(abi.encodeWithSelector(IERC20.transfer.selector, contractWallet, dy));
            require(success, "C16");
        }
        _tip(tip);
    }
    function curveSwap2DL(uint256 tip, address pool, int128 i, int128 j, uint256 dx, uint256 minDy, bool wrapEth, address tokenIn, address tokenOut, uint256 deadline)
        external payable ensure(deadline) { curveSwap2(tip, pool, i, j, dx, minDy, wrapEth, tokenIn, tokenOut); }
    /// @notice Curve swap with WETH unwrapping for ETH input, guarded by a deadline.
    /// @custom:original-selector 0xf1fe2eeb
    function recovered_9godbg900000(uint256 tip, address pool, int128 i, int128 j, uint256 dx, uint256 minDy, address tokenOut, uint256 deadline)
        external payable ensure(deadline) { recovered_gl44id100000(tip, pool, i, j, dx, minDy, tokenOut); }
    /// @notice Pull WETH from inventory, unwrap, and execute an ETH-input Curve swap.
    /// @custom:original-selector 0xfc8b5d11
    function recovered_gl44id100000(uint256 tip, address pool, int128 i, int128 j, uint256 dx, uint256 minDy, address tokenOut)
        public payable whenActive onlyCurvePool(pool) onlyOperator {
        WETHAddress.call(abi.encodeWithSelector(IERC20.transferFrom.selector, contractWallet, address(this), dx));
        WETHAddress.call(abi.encodeWithSignature("withdraw(uint256)", dx));
        uint256 dy = ICurveReturn(pool).exchange{value: dx}(i, j, dx, minDy);
        (bool success,) = tokenOut.call(abi.encodeWithSelector(IERC20.transfer.selector, contractWallet, dy));
        require(success, "C16");
        _tip(tip);
    }
    function balancerSwapV1(uint256 tip, address pool, address tokenIn, address tokenOut, uint256 amountIn, uint256 minOut, uint256 maxPrice)
        public payable whenActive onlyBalancerV1Pool(pool) onlyOperator {
        tokenIn.call(abi.encodeWithSelector(IERC20.transferFrom.selector, contractWallet, address(this), amountIn));
        (uint256 amountOut,) = IBalancerV1(pool).swapExactAmountIn(tokenIn, amountIn, tokenOut, minOut, maxPrice);
        (bool success,) = tokenOut.call(abi.encodeWithSelector(IERC20.transfer.selector, contractWallet, amountOut));
        require(success, "C16");
        _tip(tip);
    }
    function balancerSwapV1DL(uint256 tip, address pool, address tokenIn, address tokenOut, uint256 amountIn, uint256 minOut, uint256 maxPrice, uint256 deadline)
        external payable ensure(deadline) { balancerSwapV1(tip, pool, tokenIn, tokenOut, amountIn, minOut, maxPrice); }
    function balancerSwapV2(uint256 tip, bytes32 poolId, address tokenIn, address tokenOut, uint256 amountIn, uint256 minOut, uint256 deadline)
        external payable whenActive onlyBalancerV2Pool(poolId) onlyOperator {
        tokenIn.call(abi.encodeWithSelector(IERC20.transferFrom.selector, contractWallet, address(this), amountIn));
        balancerVault.swap(
            IBalancerVault.SingleSwap(poolId, IBalancerVault.SwapKind.GIVEN_IN, IAsset(tokenIn), IAsset(tokenOut), amountIn, ""),
            IBalancerVault.FundManagement(address(this), false, payable(contractWallet), false), minOut, deadline
        );
        _tip(tip);
    }
    function _tip(uint256 tip) internal {
        if (tip == 0) return;
        require(_approvedCoinbaseAddresses[block.coinbase], "C17");
        block.coinbase.call{value: tip, gas: 0}("");
    }
}
