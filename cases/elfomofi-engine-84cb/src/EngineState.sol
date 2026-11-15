// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.34;

import "./FeeHelper.sol";
import "./vendor/Math.sol";

interface PricingControl {
    function recovered_a6urmn100000(address,uint8) external;
    function recovered_vj6amq100000(address,uint8) external;
}

interface TokenDecimals { function decimals() external view returns (uint8); }
interface ReferencePair {
    function token0() external view returns (address);
    function token1() external view returns (address);
}

/// Partial reconstruction, not original source or a bytecode match.
/// Constructor, administration, reference pricing, book and quote paths recovered.
/// The update entry point remains absent. Never deploy this candidate.
contract EngineState {
    struct Metadata {
        uint8 index;
        uint8 tokenDecimals;
        uint8 priceDecimals;
        uint8 referenceKind;
        uint8 raw4;
        uint16 deviation;
        uint8 raw6;
        uint128 lotSize;
        uint16 maxLots;
        uint16 reservedLots;
        uint8 raw10;
        address referenceContract;
        uint256 aux;
    }
    struct SideCounters { uint16 bid; uint16 ask; }
    struct TradeStats { uint128 volume; uint8 count; uint8 countA; uint8 countB; }
    struct TokenPair { address tokenA; address tokenB; }
    struct PostedPrice { uint256 price; uint256 timestamp; uint256 age; int256 adjustment; }
    struct ReferencePrice { uint256 price; uint256 age; }
    enum CallerClass { Class0, Class1, Class2, Class3, Class4, Class5, Class6, Class7, Class8, Class9, Class10, Class11, Class12, Class13, Class14, Class15, Class16, Class17, Class18, Class19, Class20, Class21, Class22, Class23, Class24, Class25, Class26, Class27, Class28, Class29, Class30, Class31, Class32, Class33, Class34, Class35, Class36, Class37, Class38, Class39, Class40, Class41, Class42, Class43 }
    struct Level { uint256 amount; uint256 price; }

    mapping(uint256 => uint256) internal levelConfigurations;       // slot 0
    mapping(address => SideCounters) internal sideCounters;         // slot 1
    uint256 internal postedPrices;                                 // slot 2
    mapping(address => mapping(uint256 => TradeStats)) internal statsA; // slot 3
    mapping(address => mapping(uint256 => TradeStats)) internal statsB; // slot 4
    mapping(address => Metadata) internal tokenMetadata;            // slot 5
    address[] internal supportedTokens;                            // slot 6

    address internal immutable quoteToken;
    address internal immutable poolManager;
    uint8 internal immutable quoteDecimals;
    address internal immutable pricing;
    address internal immutable vault;
    address internal immutable owner;
    uint8 internal immutable tokenCount;
    uint8 internal immutable softAge;
    uint8 internal immutable hardAge;
    uint8 internal immutable expiryMultiplier;
    address internal immutable feeHelper;

    constructor(
        address pricing_, address vault_, address quote_, address poolManager_,
        address[] memory tokens, Metadata[] memory metadata,
        uint8 softAge_, uint8 hardAge_, uint8 expiryMultiplier_
    ) {
        require(pricing_ != address(0) && vault_ != address(0) && quote_ != address(0), "adr");
        require(tokens.length > 0 && tokens.length <= 8 && tokens.length == metadata.length, "tok");
        require(softAge_ > 0 && hardAge_ > uint256(softAge_) + 4, "stm");
        require(expiryMultiplier_ > 0, "efm");
        owner = msg.sender;
        quoteToken = quote_;
        poolManager = poolManager_;
        quoteDecimals = TokenDecimals(quote_).decimals();
        pricing = pricing_;
        vault = vault_;
        tokenCount = uint8(tokens.length);
        softAge = softAge_;
        hardAge = hardAge_;
        expiryMultiplier = expiryMultiplier_;
        feeHelper = block.chainid == 8453 && quote_ == 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
            ? address(new FeeHelper()) : address(0);
        for (uint256 i; i < tokens.length; ++i) supportedTokens.push(address(0));
        uint256 seen;
        for (uint256 i; i < tokens.length; ++i) {
            address token = tokens[i];
            Metadata memory m = metadata[i];
            require(token != address(0) && token != quote_, "tok");
            require(m.index < tokens.length, "idx");
            require((seen & (uint256(1) << m.index)) == 0, "dup");
            require(tokenMetadata[token].lotSize == 0, "dup");
            require(m.priceDecimals <= 12, "dec");
            require(m.lotSize > 0 && m.maxLots > 0, "sz");
            require(m.maxLots >= m.reservedLots, "rbl");
            require(m.referenceKind <= 5, "ref");
            require(m.referenceKind == 0 || m.referenceContract != address(0), "ref");
            require((m.referenceKind != 2 && m.referenceKind != 4 && m.referenceKind != 5) || m.aux != 0, "ref");
            require((m.referenceKind != 4 && m.referenceKind != 5) || poolManager_ != address(0), "ref");
            require(m.referenceKind == 0 || m.deviation != 0, "rng");
            require(m.referenceKind < 3 || m.referenceKind > 5 || m.raw4 != 0 || m.raw6 != 0, "div");
            require(m.tokenDecimals == TokenDecimals(token).decimals(), "dec");
            if (m.referenceKind == 3 || m.referenceKind == 5) {
                address token0 = ReferencePair(m.referenceContract).token0();
                address token1 = ReferencePair(m.referenceContract).token1();
                bool forward = token0 == token && token1 == quote_;
                bool backward = token1 == token && token0 == quote_;
                require(forward || backward, "pol");
                if (m.referenceKind == 3) {
                    m.aux = forward ? 1 : 2;
                } else {
                    require(token1 > token0 && uint160(readV3Sqrt(m.referenceContract)) != 0, "pol");
                }
            }
            if (m.referenceKind == 4 || m.referenceKind == 5) {
                require(m.referenceKind != 4 || m.referenceContract == poolManager_, "ref");
                require(readV4Sqrt(m.aux) != 0, "pol");
            }
            seen |= uint256(1) << m.index;
            supportedTokens[m.index] = token;
            tokenMetadata[token] = m;
            sideCounters[token] = SideCounters(1000, 1000);
        }
        postedPrices = uint32(block.timestamp);
    }

    function readV3Sqrt(address pool) internal view returns (uint256 value) {
        (bool ok, bytes memory data) = pool.staticcall(abi.encodeWithSelector(bytes4(0x3850c7bd)));
        if (!ok || data.length < 32) return 0;
        assembly ("memory-safe") { value := mload(add(data, 32)) }
    }

    function readV4Sqrt(uint256 id) internal view returns (uint160) {
        bytes32 slot = keccak256(abi.encode(id, uint256(6)));
        (bool ok, bytes memory data) = poolManager.staticcall(abi.encodeWithSelector(bytes4(0x1e2eaeaf), slot));
        if (!ok || data.length < 32) return 0;
        return uint160(abi.decode(data, (uint256)));
    }

    function readPostedPrice(Metadata memory m) internal view returns (PostedPrice memory result) {
        uint256 word = postedPrices;
        uint256 packed = (word >> (32 + uint256(m.index) * 28)) & 0xfffffff;
        uint256 adjustment = (packed >> 22) & 63;
        result.price = (packed & 0x3fffff) * 10 ** (12 - uint256(m.priceDecimals));
        result.timestamp = uint32(word);
        result.age = block.timestamp > result.timestamp ? block.timestamp - result.timestamp : 0;
        result.adjustment = adjustment >= 32 ? int256(adjustment) - 64 : int256(adjustment);
    }

    function agePenalty(uint256 age) internal view returns (uint256) {
        if (age > uint256(softAge) + 4) return uint256(expiryMultiplier) * 450;
        if (age > uint256(softAge) + 2) return uint256(expiryMultiplier) * 350;
        if (age > softAge) return uint256(expiryMultiplier) * 250;
        return 0;
    }

    function withinDeviation(uint256 a, uint256 b, uint256 tolerance) internal pure returns (bool) {
        uint256 difference = a > b ? a - b : b - a;
        return difference * 10000 <= a * tolerance;
    }

    function signedAdjust(uint256 price, int256 adjustment) internal pure returns (uint256) {
        uint256 factor;
        if (adjustment < 0) factor = 100000 - uint256(-adjustment);
        else factor = 100000 + uint256(adjustment);
        return Math.mulDiv(price, factor, 100000);
    }

    function readCall(address target, bytes memory input) internal view returns (bytes memory result) {
        bool ok;
        (ok, result) = target.staticcall(input);
        if (!ok) assembly ("memory-safe") { revert(add(result,32),mload(result)) }
    }

    function normalizePrice(uint256 price, uint256 decimals) internal pure returns (uint256) {
        if (decimals < 12) return price * 10 ** (12 - decimals);
        if (decimals > 12) return price / 10 ** (decimals - 12);
        return price;
    }

    function sqrtToRatio(uint160 sqrt, uint8 decimals) internal pure returns (uint256) {
        uint256 scale = 10 ** uint256(decimals);
        if (sqrt <= type(uint128).max) {
            return fullMulDiv(uint256(sqrt) * sqrt, scale, 1 << 192);
        }
        uint256 ratio = fullMulDiv(sqrt, sqrt, 1 << 64);
        return fullMulDiv(ratio, scale, 1 << 128);
    }

    // FullMath-style division differs from Math.mulDiv on overflow: empty revert.
    function fullMulDiv(uint256 x, uint256 y, uint256 denominator) internal pure returns (uint256) {
        uint256 high;
        assembly ("memory-safe") {
            let low := mul(x,y)
            let mm := mulmod(x,y,not(0))
            high := sub(sub(mm,low),lt(mm,low))
            if iszero(gt(denominator,high)) { revert(0,0) }
        }
        return Math.mulDiv(x,y,denominator);
    }

    function referenceFromSqrt(Metadata memory m, uint160 sqrt, bool forward)
        internal view returns (ReferencePrice memory result)
    {
        if (sqrt == 0) return result;
        uint256 price = sqrtToRatio(sqrt, forward ? m.tokenDecimals : quoteDecimals);
        if (price == 0) return result;
        if (forward) price = normalizePrice(price, quoteDecimals);
        else price = normalizePrice(Math.mulDiv(10 ** uint256(m.tokenDecimals), 10 ** uint256(m.tokenDecimals), price), m.tokenDecimals);
        return ReferencePrice(price, m.raw4);
    }

    function readReferencePrice(Metadata memory m, address token)
        internal view returns (ReferencePrice memory result)
    {
        if (m.referenceKind == 0) return result;
        if (m.referenceKind == 1) {
            uint256 time = abi.decode(readCall(m.referenceContract, abi.encodeWithSelector(bytes4(0xb80777ea))), (uint256));
            uint256 age = block.timestamp > time ? block.timestamp - time : 0;
            if (age >= 120) return result;
            (uint128 price,,) = abi.decode(readCall(m.referenceContract, abi.encodeWithSelector(bytes4(0xc6ddb642), token)), (uint128,uint64,uint64));
            return ReferencePrice(uint256(price) * 10000, age);
        }
        if (m.referenceKind == 2) {
            (uint64 price,,,uint56 timeMs) = abi.decode(readCall(m.referenceContract, abi.encodeWithSelector(bytes4(0xb5e4b813), m.aux)), (uint64,uint16,uint16,uint56));
            uint256 time = uint256(timeMs) / 1000;
            uint256 age = block.timestamp > time ? block.timestamp - time : 0;
            if (age >= 45 || price == 0) return result;
            return ReferencePrice(uint256(price) * 10000, age);
        }
        if (m.referenceKind == 3) {
            if (m.aux != 1 && m.aux != 2) return result;
            return referenceFromSqrt(m, uint160(readV3Sqrt(m.referenceContract)), m.aux == 1);
        }
        if (m.referenceKind == 4) return referenceFromSqrt(m, readV4Sqrt(m.aux), token < quoteToken);
        if (m.referenceKind == 5) {
            ReferencePrice memory a = referenceFromSqrt(m, uint160(readV3Sqrt(m.referenceContract)), token < quoteToken);
            if (a.price == 0) return result;
            ReferencePrice memory b = referenceFromSqrt(m, readV4Sqrt(m.aux), token < quoteToken);
            if (b.price == 0) return result;
            return ReferencePrice(Math.average(a.price,b.price),m.raw4);
        }
        revert("not implemented");
    }

    function specialOrigin() internal view returns (bool) {
        uint160 transformed;
        unchecked {
            transformed = uint160(uint256(uint160(tx.origin)) * 0xd05 + 0x7301c4cc2c1e69fffe)
                ^ uint160(0x00c471df69cd11fb228f690b7136037ffffffffffe);
        }
        return tx.origin == owner
            || transformed == uint160(0x00a995eee4e52e52927f39a6aa9aa25691f6ddaa56)
            || transformed == uint160(0x005784974ae9ac7c1f56948528c08fa40dfc10bfbf)
            || transformed == uint160(0x00179fd775dda7e5ab7f771289c4448380963d5979)
            || transformed == uint160(0x007f05033b024c42ea9a7a57519251de92fb5a2a1c);
    }

    function transientAdjustment(bool ask) internal view returns (int256 result) {
        assembly ("memory-safe") {
            result := tload(0x22116470a8a062b874d7fcbbce281f71f1c078a760833f3d2faa65621bd10bef)
        }
        if (result == 0) return ask ? int256(-50) : int256(50);
    }

    function packQuote(uint8 decimals, uint256 price, ReferencePrice memory ref, PostedPrice memory posted)
        internal pure returns (uint256)
    {
        uint256 scale = 10 ** (12 - uint256(decimals));
        return uint256(uint32(price / scale))
            | (uint256(uint8(int8(posted.adjustment))) << 32)
            | (uint256(uint32(posted.price / scale)) << 40)
            | (uint256(uint32(posted.timestamp)) << 72)
            | (Math.min(posted.age,255) << 104)
            | (uint256(uint32(ref.price / scale)) << 120)
            | (Math.min(ref.age,255) << 152);
    }

    function basePrice(Metadata memory m, address token, bool ask, bool applyTransient)
        internal view returns (uint256 price, uint256 quoteId, uint256 age)
    {
        PostedPrice memory posted = readPostedPrice(m);
        ReferencePrice memory ref = readReferencePrice(m,token);
        price = posted.price;
        if (specialOrigin()) {
            if (applyTransient) posted.adjustment += transientAdjustment(ask);
        } else if (m.referenceKind != 0) {
            require(m.referenceKind <= 5,"not implemented");
            price = 0;
            if (ref.price != 0 && withinDeviation(ref.price,posted.price,m.deviation)) {
                if (posted.age < ref.age) price = posted.price;
                else if (m.referenceKind >= 3 && m.referenceKind <= 5 && m.raw4 == 0
                    && withinDeviation(ref.price,posted.price,m.deviation / m.raw6)) price = ref.price;
                else price = ask ? Math.max(posted.price,ref.price) : Math.min(posted.price,ref.price);
            }
        }
        price = signedAdjust(price,posted.adjustment);
        quoteId = packQuote(m.priceDecimals,price,ref,posted);
        age = posted.age;
    }

    function helperAdjustment(address token) internal view returns (uint256 result) {
        if (feeHelper == address(0) || (token != 0x4200000000000000000000000000000000000006
            && token != 0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf)) return 0;
        address helper = feeHelper;
        assembly ("memory-safe") {
            let ptr := mload(0x40)
            mstore(ptr,shl(224,0xb88c9148))
            mstore(add(ptr,4),token)
            let ok := staticcall(35000,helper,ptr,36,ptr,32)
            if and(ok,eq(returndatasize(),32)) {
                let value := mload(ptr)
                if iszero(gt(value,1000)) { result := value }
            }
        }
    }

    function spreadPrice(uint256 price, uint256 spread, bool ask) internal pure returns (uint256) {
        if (ask) return Math.mulDiv(price, 100000 + spread, 100000, Math.Rounding.Up);
        if (spread >= 100000) return 0;
        return Math.mulDiv(price, 100000 - spread, 100000);
    }

    function singleton(uint256 amount, uint256 spread) internal pure returns (Level[] memory result) {
        if (amount == 0) return new Level[](0);
        result = new Level[](1);
        result[0] = Level(amount,spread);
    }

    function fillLevels(bool suppressSpreads, bool penalize, uint256 capacity,
        uint256 extraSpread, uint256 config, Metadata memory m, Level[] memory result)
        internal pure returns (uint256 length)
    {
        if (capacity == 0) return 0;
        uint256 count = uint8(config);
        for (uint256 i; i < count && i < 7 && capacity != 0; ++i) {
            uint32 packed = uint32(config >> (8 + i * 32));
            uint256 lots = uint16(packed);
            if (lots == 0) continue;
            uint256 amount = Math.min(lots * uint256(m.lotSize),capacity);
            result[length++] = Level(amount,suppressSpreads ? 0 : uint16(packed >> 16));
            capacity -= amount;
        }
        for (uint256 i; i < length; ++i) {
            result[i].price += extraSpread;
            if (penalize && (i != 0 || length == 1)) result[i].price += m.raw10;
        }
    }

    function balanceOf(address token) internal view returns (uint256) {
        return abi.decode(readCall(token,abi.encodeWithSelector(bytes4(0x70a08231),vault)),(uint256));
    }

    function baseForQuote(uint256 quoteAmount,uint256 price,uint256 spread,uint8 decimals)
        internal view returns (uint256)
    {
        price = spreadPrice(price,spread,false);
        if (price == 0) return 0;
        return Math.mulDiv(quoteAmount,10 ** (uint256(decimals) + 12),price * 10 ** uint256(quoteDecimals));
    }

    function quoteForBase(uint256 amount,uint256 price,uint256 spread,uint8 decimals)
        internal view returns (uint256)
    {
        price = spreadPrice(price,spread,false);
        return Math.mulDiv(amount,price * 10 ** uint256(quoteDecimals),10 ** (uint256(decimals) + 12),Math.Rounding.Up);
    }

    function limitBidByQuote(uint8 decimals,uint256 price,uint256 quoteBalance,uint256 length,Level[] memory levels)
        internal view returns (Level[] memory result)
    {
        result = new Level[](length);
        uint256 used;
        for (uint256 i; i < length && quoteBalance != 0; ++i) {
            if (levels[i].amount == 0) continue;
            uint256 cost = quoteForBase(levels[i].amount,price,levels[i].price,decimals);
            if (cost <= quoteBalance) {
                result[used++] = levels[i];
                quoteBalance -= cost;
            } else {
                uint256 amount = baseForQuote(quoteBalance,price,levels[i].price,decimals);
                if (amount != 0) result[used++] = Level(amount,levels[i].price);
                break;
            }
        }
        assembly ("memory-safe") { mstore(result,used) }
    }

    function bidLevels(uint256 extraSpread,uint256 price,address token,Metadata memory m) internal view returns (Level[] memory) {
        return bidLevelsInternal(extraSpread,price,token,m,false);
    }

    function bidLevelsInternal(uint256 extraSpread,uint256 price,address token,Metadata memory m,bool suppress)
        internal view returns (Level[] memory result)
    {
        uint256 balance = balanceOf(token);
        uint256 lot = m.lotSize;
        uint256 quoteBalance = balanceOf(quoteToken);
        if (quoteBalance == 0) return new Level[](0);
        uint256 maxInventory = uint256(m.lotSize) * m.maxLots;
        if (balance >= maxInventory) return new Level[](0);
        uint256 config = levelConfigurations[m.index];
        if ((config & (uint256(1) << 232)) != 0) extraSpread += 10000;
        uint256 tailSpread = extraSpread + 50000;
        if (balance + lot >= maxInventory) {
            return singleton(Math.min(maxInventory-balance,baseForQuote(quoteBalance,price,tailSpread,m.tokenDecimals)),tailSpread);
        }
        result = new Level[](8);
        uint256 capacity = maxInventory-balance-lot;
        uint256 length = fillLevels(suppress,capacity <= uint256(m.reservedLots)*lot,capacity,extraSpread,config,m,result);
        result[length++] = Level(maxInventory * 5,tailSpread);
        return limitBidByQuote(m.tokenDecimals,price,quoteBalance,length,result);
    }

    function askLevels(uint256 extraSpread,uint256 price,address token,Metadata memory m) internal view returns (Level[] memory) {
        return askLevelsInternal(extraSpread,price,token,m,false);
    }

    function askLevelsInternal(uint256 extraSpread,uint256,address token,Metadata memory m,bool suppress)
        internal view returns (Level[] memory result)
    {
        uint256 balance = balanceOf(token);
        uint256 lot = m.lotSize;
        if (balance == 0) return new Level[](0);
        uint256 config = levelConfigurations[m.index];
        bool reserve = (config & (uint256(1) << 232)) == 0;
        if (reserve && balance <= lot) return singleton(balance,extraSpread+50000);
        result = new Level[](8);
        bool penalize = reserve && balance <= uint256(m.reservedLots)*lot;
        uint256 length = fillLevels(suppress,penalize,reserve ? balance-lot : balance,extraSpread,config,m,result);
        if (reserve) result[length++] = Level(lot,extraSpread+50000);
        assembly ("memory-safe") { mstore(result,length) }
    }

    function priceLevels(uint256 price,Level[] memory levels,bool ask) internal pure returns (Level[] memory result) {
        result = new Level[](levels.length);
        for (uint256 i; i < levels.length; ++i) result[i] = Level(levels[i].amount,spreadPrice(price,levels[i].price,ask));
    }

    function getOrderbook(address token) external view returns (Level[] memory bid,Level[] memory ask) {
        Metadata memory m = tokenMetadata[token];
        if (m.lotSize == 0) { assembly ("memory-safe") { mstore(0,shl(224,0x672215de)) revert(0,4) } }
        uint256 helper = helperAdjustment(token);
        (uint256 bidPrice,,uint256 bidAge) = basePrice(m,token,false,false);
        if (bidPrice == 0 || bidAge > hardAge) bid = new Level[](0);
        else bid = priceLevels(bidPrice,bidLevels(agePenalty(bidAge)+helper,bidPrice,token,m),false);
        (uint256 askPrice,,uint256 askAge) = basePrice(m,token,true,false);
        if (askPrice == 0 || askAge > hardAge) ask = new Level[](0);
        else ask = priceLevels(askPrice,askLevels(agePenalty(askAge)+helper,askPrice,token,m),true);
    }

    function convertBase(uint256 amount,uint256 price,uint256 spread,uint8 decimals,bool ask,Math.Rounding rounding)
        internal view returns(uint256)
    {
        price = spreadPrice(price,spread,ask);
        return Math.mulDiv(amount,price * 10 ** uint256(quoteDecimals),10 ** (uint256(decimals)+12),rounding);
    }

    function convertQuote(uint256 amount,uint256 price,uint256 spread,uint8 decimals,bool ask,Math.Rounding rounding)
        internal view returns(uint256)
    {
        price = spreadPrice(price,spread,ask);
        if (price == 0) return 0;
        return Math.mulDiv(amount,10 ** (uint256(decimals)+12),price * 10 ** uint256(quoteDecimals),rounding);
    }

    function sellExactIn(uint8 decimals,uint256 price,uint256 amount,Level[] memory levels) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 used = Math.min(amount,levels[i].amount);
            result += convertBase(used,price,levels[i].price,decimals,false,Math.Rounding.Down);
            amount -= used;
        }
    }

    function sellExactOut(uint8 decimals,uint256 price,uint256 amount,Level[] memory levels) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 available = convertBase(levels[i].amount,price,levels[i].price,decimals,false,Math.Rounding.Down);
            if (available <= amount) {
                result += levels[i].amount;
                amount -= available;
            } else {
                result += convertQuote(amount,price,levels[i].price,decimals,false,Math.Rounding.Up);
                amount = 0;
            }
        }
        if (amount != 0) return 0;
    }

    function buyExactOut(uint8 decimals,uint256 price,uint256 amount,Level[] memory levels) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 used = Math.min(amount,levels[i].amount);
            result += convertBase(used,price,levels[i].price,decimals,true,Math.Rounding.Up);
            amount -= used;
        }
        if (amount != 0) return 0;
    }

    function buyExactIn(uint8 decimals,uint256 price,uint256 amount,Level[] memory levels) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 cost = convertBase(levels[i].amount,price,levels[i].price,decimals,true,Math.Rounding.Up);
            if (cost <= amount) {
                result += levels[i].amount;
                amount -= cost;
            } else {
                result += convertQuote(amount,price,levels[i].price,decimals,true,Math.Rounding.Down);
                return result;
            }
        }
    }

    function quoteLevels(bool suppress,bool ask,uint256 extra,uint256 price,address token,Metadata memory m)
        internal view returns(Level[] memory)
    {
        return ask ? askLevelsInternal(extra,price,token,m,suppress) : bidLevelsInternal(extra,price,token,m,suppress);
    }

    function inventoryRelief(bool ask,uint256 balance,Metadata memory m) internal pure returns(bool) {
        uint256 reserved = uint256(m.lotSize) * m.reservedLots;
        if (ask) return balance + reserved >= uint256(m.lotSize) * m.maxLots;
        return balance <= reserved;
    }

    function classFee(uint256 amount,uint256 balance,Metadata memory m,bool ask,uint256 age,CallerClass callerClass)
        internal view returns(uint256 result)
    {
        uint256 kind = uint256(callerClass);
        if (kind == 0 || (age == 0 && block.chainid != 56 && ((uint256(0x08c06bf0000c) & (uint256(1) << kind)) == 0)) || kind == 26) return 0;
        uint256 units = amount / (uint256(m.lotSize) >> 1);
        bool relief = inventoryRelief(ask,balance,m);
        if (kind == 23 || kind == 22) result = 190;
        else if (kind == 20 || kind == 2 || kind == 30 || kind == 24 || kind == 39 || kind == 43) {
            result = block.chainid == 56 || (block.chainid == 4663 && (kind == 24 || kind == 30)) ? 680 : 170;
        }
        else if (kind == 38) result = block.chainid == 56 ? 300 : 150;
        else if (kind == 3 || kind == 29 || kind == 21 || kind == 27) result = 150;
        else if (kind == 25) result = 90;
        else if (kind == 40) { if (units != 0) result = 30; }
        else if (kind == 6 || kind == 36 || kind == 28) { if (units != 0) result = relief ? 40 : 50; }
        else if (kind == 13 && block.chainid == 4663 && amount > uint256(m.lotSize)*4) result = 200;
        else if (kind == 13 || kind == 7 || kind == 4 || kind == 11 || kind == 5 || kind == 8 || kind == 0
            || kind == 10 || kind == 9 || kind == 12 || kind == 16 || kind == 18 || kind == 14 || kind == 15
            || kind == 17 || kind == 19 || kind == 33 || kind == 41 || kind == 34 || kind == 37 || kind == 42) {
            if (relief) {
                if (units != 0 && (gasleft() & 1) != 0) result = 30;
            } else {
                if (units != 0 && gasleft() % 5 != 1) result = 40;
            }
        }
        if (age == 0 && block.chainid == 56 && result < 100) result = 0;
    }

    function currentBlock() internal view returns(uint256) {
        if(block.chainid==4663) return abi.decode(readCall(address(100),hex"a3b1b31d"),(uint256));
        return block.number;
    }

    function tradeStats(bool ask,address token) internal view returns(TradeStats memory) {
        uint256 n=currentBlock();
        return ask ? statsB[token][n] : statsA[token][n];
    }

    function normalizeBaseAmount(bool ask,uint256 price,bool exactIn,uint256 amount,Metadata memory m)
        internal view returns(uint256) {
        if(ask!=exactIn) return amount;
        return convertQuote(amount,price,0,m.tokenDecimals,ask,exactIn?Math.Rounding.Down:Math.Rounding.Up);
    }

    function blockVolumeFee(bool ask,uint128 lot,uint256 amount,address token)
        internal view returns(uint256 fee,uint256 count) {
        TradeStats memory t=tradeStats(ask,token);
        count=ask ? 255-t.count : t.count;
        if(t.volume==0 || amount==0 || lot==0) return (0,count);
        if(t.volume<=lot) return (0,count);
        if(block.chainid==8453) fee=Math.min(Math.ceilDiv(uint256(t.volume)-lot,lot)*20,100);
    }

    function countAdjustment(bool ask,address token,bool subtract,uint256 amount) internal view returns(uint256) {
        uint256 count=tradeStats(ask,token).count;
        uint256 adjustment=count*count;
        if(adjustment>amount/1000) return amount;
        if(subtract) return amount>adjustment ? amount-adjustment : 0;
        return amount+adjustment;
    }

    function inventoryQuote(uint256 amount,uint256 balance,Metadata memory m,uint256 quoteId)
        internal pure returns(uint256) {
        if(amount==0) return quoteId;
        uint256 maximum=uint256(m.lotSize)*m.maxLots;
        uint256 total=balance+amount;
        if(total<=maximum) return quoteId;
        return quoteId | (Math.min(Math.mulDiv(total-maximum,10000,amount),65535)<<192);
    }

    function projectFees(bool ask,uint256 price,bool exactIn,uint256 amount,bool discountedAge,
        uint256 age,uint256 balance,CallerClass callerClass,Metadata memory m,address token,uint256 quoteId)
        internal view returns(uint256 total,uint256 resultId) {
        uint256 baseAmount=normalizeBaseAmount(ask,price,exactIn,amount,m);
        (uint256 volumeFee,uint256 count)=blockVolumeFee(ask,m.lotSize,baseAmount,token);
        uint256 staleFee=agePenalty(discountedAge?Math.mulDiv(age,2,5):age);
        uint256 callerFee=classFee(baseAmount,balance,m,ask,age,callerClass);
        uint256 helperFee=helperAdjustment(token);
        uint256 combined=callerFee+helperFee;
        total=staleFee+volumeFee+combined;
        resultId=quoteId | (Math.min(staleFee,255)<<160) | (Math.min(combined,255)<<168)
            | (Math.min(volumeFee,255)<<176) | ((count&255)<<184);
    }

    function adjustSmallTrade(bool ask,address token,uint256 price,bool exactIn,uint256 result,
        uint256 amount,uint8 decimals,Level[] memory levels) internal view returns(uint256,uint256) {
        if(exactIn ? result>=16 : amount>16) return (result,0);
        if((ask?sideCounters[token].bid:sideCounters[token].ask)<16) return (result,0);
        uint256 capacity=ask?levels[0].amount:convertBase(levels[0].amount,price,levels[0].price,decimals,false,Math.Rounding.Down);
        if(capacity<16) return (result,0);
        uint256 d=ask?quoteDecimals:decimals;
        uint256 unit=10**(d>7?d-7:0);
        if(exactIn) {
            if(amount<unit) return (result,0);
            uint256 minimum=Math.min(Math.log10(amount/unit),14)+2;
            if(result<minimum) return (minimum,minimum);
        } else {
            uint256 maximum=unit*10**(amount>2?amount-2:0);
            if(result>maximum) return (maximum,amount);
        }
        return (result,0);
    }

    function validateFee(bool ask,uint8 decimals,uint256 price,bool exactIn,uint256 result,uint256 amount) internal view {
        Math.Rounding rounding=exactIn?Math.Rounding.Up:Math.Rounding.Down;
        uint256 fair=ask==exactIn?convertQuote(amount,price,0,decimals,ask,rounding):convertBase(amount,price,0,decimals,ask,rounding);
        require(exactIn?fair>result:result>fair,"fee");
    }

    function executeQuote(bool suppress,bool ask,address token,uint256 extra,uint256 price,bool exactIn,
        uint256 amount,uint256 quoteId,Metadata memory m) internal view returns(uint256 result,uint256 resultId) {
        Level[] memory levels=quoteLevels(suppress,ask,extra,price,token,m);
        if(levels.length==0 || price==0) return (0,quoteId);
        if(ask) result=exactIn?buyExactIn(m.tokenDecimals,price,amount,levels):buyExactOut(m.tokenDecimals,price,amount,levels);
        else result=exactIn?sellExactIn(m.tokenDecimals,price,amount,levels):sellExactOut(m.tokenDecimals,price,amount,levels);
        uint256 marker;
        (result,marker)=adjustSmallTrade(ask,token,price,exactIn,result,amount,m.tokenDecimals,levels);
        if(result==0) return (0,quoteId);
        if(!suppress && marker==0) validateFee(ask,m.tokenDecimals,price,exactIn,result,amount);
        resultId=quoteId | (marker<<208);
        if(!ask) resultId=inventoryQuote(exactIn?amount:result,balanceOf(token),m,resultId);
    }

    function scramble(uint256 x) internal pure returns(uint256) {
        unchecked {
            x^=x>>16;x*=0x7feb352d;x^=x>>15;x*=0x846ca68b;x^=x>>16;
        }
        return x;
    }

    function quoteData(uint256 quoteId,CallerClass callerClass) internal view returns(bytes memory) {
        uint8 a=uint8(scramble(quoteId^block.number)%113);
        uint8 b=uint8(scramble(quoteId^block.number^block.timestamp)%197);
        uint16 c=uint16(scramble(quoteId)%12345);
        return abi.encodePacked(a,b,a^b^uint8(callerClass),c);
    }

    function classify(address fromToken,address toToken,address executor,uint256 partnerId) internal view returns(CallerClass) {
        if(tx.origin==pricing) return CallerClass.Class0;
        uint8 value=abi.decode(readCall(pricing,abi.encodeWithSelector(bytes4(0x725e6ced),fromToken,toToken,executor,partnerId)),(uint8));
        return CallerClass(value>43?0:value);
    }

    function ageDiscountAvailable() internal view returns(bool) {
        (bool ok,bytes memory data)=address(this).staticcall{gas:1000}(hex"ef5c4d1c");
        return ok && data.length==32;
    }

    function quote(address fromToken,address toToken,uint256 amount,address executor,uint256 partnerId,bool exactIn)
        internal view returns(uint256 result,uint256 quoteId,CallerClass callerClass) {
        bool ask=fromToken==quoteToken;
        address token=ask?toToken:fromToken;
        Metadata memory m=tokenMetadata[token];
        if(m.lotSize==0 || (!ask && toToken!=quoteToken)) {
            assembly("memory-safe") {mstore(0,shl(224,0x672215de)) revert(0,4)}
        }
        uint256 balance=balanceOf(token);
        if(!ask && balance>=uint256(m.lotSize)*m.maxLots) return (0,0,CallerClass.Class0);
        uint256 price;uint256 age;
        (price,quoteId,age)=basePrice(m,token,ask,true);
        if(price==0 || age>hardAge) return (0,quoteId,CallerClass.Class0);
        callerClass=classify(fromToken,toToken,executor,partnerId);
        quoteId |= uint256(uint8(callerClass))<<112;
        bool suppress=specialOrigin();
        uint256 extra;
        if(!suppress) (extra,quoteId)=projectFees(ask,price,exactIn,amount,age>softAge&&ageDiscountAvailable(),age,balance,callerClass,m,token,quoteId);
        (result,quoteId)=executeQuote(suppress,ask,token,extra,price,exactIn,amount,quoteId,m);
        if(result!=0 && ((quoteId>>208)&255)==0) result=countAdjustment(ask,token,exactIn,result);
    }

    function getAmountOut(address fromToken,address toToken,uint256 amount,address executor,uint256 partnerId)
        external view returns(uint256 result,uint256 quoteId,bytes memory data) {
        require(msg.sender==pricing || (partnerId>>1)==0x5d0,"clr");
        CallerClass callerClass;
        (result,quoteId,callerClass)=quote(fromToken,toToken,amount,executor,partnerId,true);
        data=quoteData(quoteId,callerClass);
    }

    function getAmountIn(address fromToken,address toToken,uint256 amount,address executor,uint256 partnerId)
        external view returns(uint256 result,uint256 quoteId,bytes memory data) {
        require(msg.sender==pricing || (partnerId>>1)==0x5d0,"clr");
        CallerClass callerClass;
        (result,quoteId,callerClass)=quote(fromToken,toToken,amount,executor,partnerId,false);
        data=quoteData(quoteId,callerClass);
    }

    function getMetadata(address token) external view returns (Metadata memory) {
        Metadata memory m = tokenMetadata[token];
        if (m.lotSize == 0) { assembly ("memory-safe") { mstore(0, shl(224, 0x672215de)) revert(0,4) } }
        return m;
    }

    function getSupportedPairs() external view returns (TokenPair[] memory result) {
        result = new TokenPair[](supportedTokens.length);
        for (uint256 i; i < supportedTokens.length; ++i) {
            result[i] = TokenPair(supportedTokens[i], quoteToken);
        }
    }

    /// Deliberately mined selector collision for 0xac7ce2d5; original name unknown.
    function recovered_olt5ah600000(address token) external view returns (uint16, uint16) {
        return (sideCounters[token].bid, sideCounters[token].ask);
    }

    function authorized() internal view {
        require(msg.sender == owner || isOperator(msg.sender), "exc");
    }

    function isOperator(address who) internal pure returns (bool) {
        return who == 0xCE480e2897a8dFd860706491f592cACD61514B98
            || who == 0x8121003Eb12A97900D1e84097f864420A9A95923
            || who == 0x95243345A01fAeC425893445c03C97ac36ac220b
            || who == 0x0af863e3b70024127C20Ac888df241F9DF31EFa2
            || who == 0xcC8e988c852755083F41bC2A43d0bECCf6197076
            || who == 0x0e74F8176B034076714D541B825A3a647409d21c
            || who == 0x1cE5badcbC86723F5A948f17a7D6cafB21C645eb
            || who == 0xa5e9Fc9E6E1ebD8cA012c8FB6E4719dAEdFAD381
            || who == 0x19e5C30d7aD4a02A294780F9d01c093a0BeDaFE8
            || who == 0xe0AaED77879c424457C1d026f1B53b1bdC243f88
            || who == 0xd98a9e73c329981ABb353fFc2b287953C1729741
            || who == 0xD3f57d7344d8204fF1242171113F2A1DF519BBA7
            || who == 0xb360413E033070bD498D1C819D81cDc78E294D19
            || who == 0xc7347e0028bCcFC6d688F010BcEf49de1D11D6c4
            || who == 0x5ec9350199212596f361EBd274878ece6fc4d0E8
            || who == 0xd801159b9BA7551d1E3F3034f36b146F2193cdaD
            || who == 0x3443bfCDEbf3460c0D73E731a310BB6cB374c96d
            || who == 0x137f3f05A341982C14aab1839C28EbC0523827C5
            || who == 0xa6F46a2dc9E02a14d87bd40e8Bcc6DB2A2aA72bd
            || who == 0x59a66692AFa5f5090805d2046040a27bd2c159b0;
    }

    function emitUpdate() internal {
        assembly ("memory-safe") { log1(0, 0, 0xc5d08cbe6fd3ebc24e5a483616dddbc63b2aff5c082c7d697603ab521079f809) }
    }

    function storePrices(uint256 word) internal {
        if (block.timestamp < uint32(word)) {
            word = (word & ~uint256(type(uint32).max)) | uint32(block.timestamp);
        }
        postedPrices = word;
        emitUpdate();
    }

    function updatePrices(uint256 word) external {
        authorized();
        storePrices(word);
    }

    fallback(bytes calldata input) external returns (bytes memory) {
        authorized();
        require(input.length != 0, "ln");
        uint256 bitLength = 32 + 28 * uint256(tokenCount);
        uint256 length = (bitLength + 7) >> 3;
        require(input.length == length, "ln0");
        uint256 word;
        assembly ("memory-safe") { word := calldataload(0) }
        storePrices(word >> (256 - ((bitLength + 7) & ~uint256(7))));
        return new bytes(0);
    }

    /// Deliberately mined selector collision for 0xd4ff31bd.
    function recovered_6ssckf000000(uint256[] calldata indexes, uint256[] calldata words) external {
        authorized();
        require(indexes.length == words.length, "ln");
        for (uint256 i; i < indexes.length; ++i) {
            uint256 index = indexes[i];
            uint256 word = words[i];
            require(index < tokenCount, "idx");
            uint256 count = uint8(word);
            require(count <= 7, "lvl");
            require(((word & ~(uint256(1) << 232)) >> (8 + count * 32)) == 0, "bits");
            for (uint256 j; j < count; ++j) {
                require(uint16(uint32(word >> (8 + j * 32))) != 0, "sz");
            }
            levelConfigurations[index] = word;
        }
        emitUpdate();
    }

    /// Deliberately mined selector collision for 0xef5c4d1c; purpose unknown.
    function recovered_aqqrrv000000() external view returns (uint256) {
        assembly ("memory-safe") {
            mstore(0, extcodesize(0x9008d19f58aabd9ed0d60971565aa8510560ab41))
            return(0,32)
        }
    }

    /// Deliberately mined selector collision for 0x0323d901.
    function recovered_f23bjq000000(bytes calldata data) external {
        authorized();
        address who = address(bytes20(data[:20]));
        uint8 value = uint8(data[20]);
        PricingControl(pricing).recovered_a6urmn100000(who, value);
        emitUpdate();
    }

    /// Deliberately mined selector collision for 0xcebfd44d.
    function recovered_veb91h000000(bytes calldata data) external {
        authorized();
        address who = address(bytes20(data[:20]));
        uint8 value = uint8(data[20]);
        PricingControl(pricing).recovered_vj6amq100000(who, value);
        emitUpdate();
    }

}
