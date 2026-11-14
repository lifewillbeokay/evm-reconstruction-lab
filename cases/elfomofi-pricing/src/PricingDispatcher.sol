// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.34;

import {IElfomoPricing} from "./IElfomoPricing.sol";

/// Independent behavioral reconstruction of Base 0x555a998a...c66790b.
/// Analyst names describe behavior; unresolved selectors remain in fallback.
/// Not original source, not bytecode-identical, and not intended for deployment.
contract PricingDispatcher is IElfomoPricing {
    uint8 private initialized;             // slot 0, byte 0
    bool private initializing;             // slot 0, byte 1
    uint256[50] private initializationGap;  // slots 1..50
    address public owner;                  // slot 51
    uint256[49] private ownershipGap;       // slots 52..100
    mapping(uint256 => address) private engines; // slot 101
    TokenPair[] private pairs;             // slot 102
    address private classifier;           // slot 103: analyst name
    address private immutable swap;
    uint256 private constant KEY_OFFSET = 0x0146109eced2816f22a2937a116619ffffffffffff;
    address private constant SPECIAL_ADMIN = 0x423429453Df78B5eD36CE1D6C1eDcBA41c3a358a;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event Initialized(uint8 version);
    error InvalidCaller();

    constructor(address swap_) {
        swap = swap_;
        initialized = type(uint8).max;
        emit Initialized(type(uint8).max);
    }
    modifier onlyOwner() {
        require(msg.sender == owner, "Ownable: caller is not the owner"); _;
    }
    modifier onlySwap() { if (msg.sender != swap) revert InvalidCaller(); _; }

    function initialize(address newOwner) external {
        bool top = !initializing;
        require((top && initialized < 1) || (address(this).code.length == 0 && initialized == 1),
            "Initializable: contract is already initialized");
        initialized = 1;
        if (top) initializing = true;
        _owner(newOwner);
        if (top) { initializing = false; emit Initialized(1); }
    }
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Ownable: new owner is the zero address");
        _owner(newOwner);
    }
    function renounceOwnership() external onlyOwner { _owner(address(0)); }
    function _owner(address next) private {
        address old = owner; owner = next; emit OwnershipTransferred(old, next);
    }
    function _key(address a, address b) private pure returns (uint256) {
        return uint256(uint160(a)) + uint256(uint160(b)) + KEY_OFFSET;
    }
    function addPair(address a, address b) external onlyOwner {
        pairs.push(TokenPair(a, b));
        _call(swap, abi.encodeWithSelector(bytes4(0xa7c87ec2), a, b));
    }
    function getSupportedPairs() external view onlySwap returns (TokenPair[] memory) { return pairs; }
    function getAmountOut(address a, address b, uint256 amount, address executor, uint256 partnerId)
        external view onlySwap returns (uint256, uint256, bytes memory) {
        address engine = engines[_key(a, b)];
        if (engine == address(0)) return (0, 0, new bytes(0));
        return IElfomoPricing(engine).getAmountOut(a, b, amount, executor, partnerId);
    }
    function getAmountIn(address a, address b, uint256 amount, address executor, uint256 partnerId)
        external view onlySwap returns (uint256, uint256, bytes memory) {
        address engine = engines[_key(a, b)];
        if (engine == address(0)) return (0, 0, new bytes(0));
        return IElfomoPricing(engine).getAmountIn(a, b, amount, executor, partnerId);
    }
    struct Level { uint256 amount; uint256 price; } // field meanings are analyst labels
    function getOrderbook(address a, address b) external view returns (Level[] memory, Level[] memory) {
        address engine = engines[_key(a, b)];
        if (engine == address(0)) return (new Level[](0), new Level[](0));
        (bool ok, bytes memory out) = engine.staticcall(abi.encodeWithSelector(bytes4(0xba88b1cc), a));
        if (!ok) _revert(out);
        return abi.decode(out, (Level[], Level[]));
    }
    function update(uint256 quoteId, bytes memory data, address a, address b,
        uint256 amountIn, uint256 amountOut, address executor, uint256 partnerId) external onlySwap {
        address engine = engines[_key(a, b)];
        if (engine == address(0)) return;
        _call(engine, abi.encodeCall(IElfomoPricing.update,
            (quoteId, data, a, b, amountIn, amountOut, executor, partnerId)));
        if (classifier != address(0)) {
            uint8 tag;
            if (data.length >= 3) tag = uint8(data[0]) ^ uint8(data[1]) ^ uint8(data[2]);
            _call(classifier, abi.encodeWithSelector(bytes4(0xb8e5cf90), tag));
        }
    }
    // Original names of these five selectors have not been recovered. This
    // fallback preserves their wire interfaces without inventing collision names.
    fallback(bytes calldata input) external returns (bytes memory output) {
        bytes4 sig = msg.sig;
        if (sig == 0x19b4c955) {
            address next = abi.decode(input[4:], (address));
            if (msg.sender != owner && msg.sender != SPECIAL_ADMIN) revert InvalidCaller();
            classifier = next;
        } else if (sig == 0x2784993c) {
            bytes memory packed = abi.decode(input[4:], (bytes));
            require(msg.sender == owner, "Ownable: caller is not the owner");
            if (packed.length < 52) assembly { revert(0, 0) }
            uint256 sum; address engine;
            assembly { sum := mload(add(packed, 32)) engine := shr(96, mload(add(packed, 64))) }
            engines[sum + KEY_OFFSET] = engine;
        } else if (sig == 0x725e6ced) {
            (address a, address b, address executor, uint256 partnerId) =
                abi.decode(input[4:], (address, address, address, uint256));
            address engine = engines[_key(a, b)];
            if (engine == address(0) || msg.sender != engine || classifier == address(0)) return abi.encode(uint8(0));
            (bool ok, bytes memory out) = classifier.staticcall(
                abi.encodeWithSelector(bytes4(0x3929cd4e), executor, partnerId));
            if (!ok) _revert(out);
            return abi.encode(abi.decode(out, (uint8)));
        } else if (sig == 0xfbecbad7 || sig == 0xd2ad58b5) {
            (address who, uint8 value) = abi.decode(input[4:], (address, uint8));
            require(tx.origin == owner || _operator(tx.origin), "exc");
            _call(classifier, abi.encodeWithSelector(
                sig == 0xfbecbad7 ? bytes4(0x066cd13f) : bytes4(0x2f115662), who, value));
        } else { assembly { revert(0, 0) } }
    }
    function _call(address to, bytes memory data) private {
        if (to.code.length == 0) assembly { revert(0, 0) }
        (bool ok, bytes memory out) = to.call(data);
        if (!ok) _revert(out);
    }
    function _revert(bytes memory out) private pure { assembly { revert(add(out, 32), mload(out)) } }
    function _operator(address who) private pure returns (bool) {
        // The deployed dispatcher has this literal set of 20 origin addresses.
        return who == 0xCE480e2897a8dFd860706491f592cACD61514B98 ||
            who == 0x59a66692AFa5f5090805d2046040a27bd2c159b0 ||
            who == 0xa6F46a2dc9E02a14d87bd40e8Bcc6DB2A2aA72bd ||
            who == 0x137f3f05A341982C14aab1839C28EbC0523827C5 ||
            who == 0x3443bfCDEbf3460c0D73E731a310BB6cB374c96d ||
            who == 0xd801159b9BA7551d1E3F3034f36b146F2193cdaD ||
            who == 0x5ec9350199212596f361EBd274878ece6fc4d0E8 ||
            who == 0xc7347e0028bCcFC6d688F010BcEf49de1D11D6c4 ||
            who == 0xb360413E033070bD498D1C819D81cDc78E294D19 ||
            who == 0xD3f57d7344d8204fF1242171113F2A1DF519BBA7 ||
            who == 0xd98a9e73c329981ABb353fFc2b287953C1729741 ||
            who == 0xe0AaED77879c424457C1d026f1B53b1bdC243f88 ||
            who == 0x19e5C30d7aD4a02A294780F9d01c093a0BeDaFE8 ||
            who == 0xa5e9Fc9E6E1ebD8cA012c8FB6E4719dAEdFAD381 ||
            who == 0x1cE5badcbC86723F5A948f17a7D6cafB21C645eb ||
            who == 0x0e74F8176B034076714D541B825A3a647409d21c ||
            who == 0xcC8e988c852755083F41bC2A43d0bECCf6197076 ||
            who == 0x0af863e3b70024127C20Ac888df241F9DF31EFa2 ||
            who == 0x95243345A01fAeC425893445c03C97ac36ac220b ||
            who == 0x8121003Eb12A97900D1e84097f864420A9A95923;
    }
}
