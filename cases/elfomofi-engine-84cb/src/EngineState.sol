// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.34;

import "./FeeHelper.sol";
import "./vendor/Math.sol";

interface PricingControl {
    function recovered_a6urmn100000(address,uint8) external;
    function recovered_vj6amq100000(address,uint8) external;
}

interface TokenBalance { function balanceOf(address) external view returns(uint256); }
interface TimestampFeed { function timestamp() external view returns(uint256); }
interface BlockSystem { function arbBlockNumber() external view returns(uint256); }
interface TokenDecimals { function decimals() external view returns (uint8); }
interface ReferencePair {
    function token0() external view returns (address);
    function token1() external view returns (address);
}

/// Independent reconstruction. Names are analytical; explorer verification is pending.
// Constructed selector collision; the original oracle function name is unknown.
interface RecoveredAddressOracle { function recovered_q54g44b00000(address) external view returns(uint128,uint64,uint64); }
// Constructed selector collision; the original oracle function name is unknown.
interface RecoveredIndexOracle { function recovered_reml0o500000(uint256) external view returns(uint64,uint16,uint16,uint56); }
contract EngineState {
    // Candidate error signature matching the captured 0x672215de selector.
    error InvalidTokens();
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
    uint256 internal immutable quoteDecimals;
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
            require(m.reservedLots <= m.maxLots, "rbl");
            require(m.referenceKind <= 5, "ref");
            require(m.referenceKind == 0 || m.referenceContract != address(0), "ref");
            require((m.referenceKind != 2 && m.referenceKind != 4 && m.referenceKind != 5) || m.aux != 0, "ref");
            require((m.referenceKind != 4 && m.referenceKind != 5) || poolManager_ != address(0), "ref");
            require(m.referenceKind == 0 || m.deviation != 0, "rng");
            require(!isPoolReference(m.referenceKind) || m.raw4 != 0 || m.raw6 != 0, "div");
            require(TokenDecimals(token).decimals() == m.tokenDecimals, "dec");
            if (m.referenceKind == 3 || m.referenceKind == 5) {
                address token0 = ReferencePair(m.referenceContract).token0();
                address token1 = ReferencePair(m.referenceContract).token1();
                bool forward = token0 == token && token1 == quote_;
                bool backward = token0 == quote_ && token1 == token;
                require(forward || backward, "pol");
                if (m.referenceKind == 3) {
                    m.aux = forward ? uint256(1) : 2;
                } else {
                    require(token1 > token0 && readV3Sqrt(m.referenceContract) != 0, "pol");
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

    function readV3Sqrt(address pool) internal view returns (uint160 value) {
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
        uint256 timestamp = uint32(word);
        uint256 packed = (word >> (32 + uint256(m.index) * 28)) & ((~uint256(0)) >> 228);
        uint256 adjustment = (packed >> uint256(22)) & 63;
        int256 tilt = adjustment >= 32 ? int256(adjustment) - 64 : int256(adjustment);
        result.price = (packed & 0x3fffff) * 10 ** (12 - uint256(m.priceDecimals));
        result.timestamp = timestamp;
        result.age = block.timestamp > result.timestamp ? block.timestamp - result.timestamp : 0;
        result.adjustment = tilt;
    }

    function expiryFactor() internal view returns(uint256) {
        return uint256(expiryMultiplier);
    }

    function agePenalty(uint256 age) internal view returns (uint256 result) {
        if (age > uint256(softAge) + 4) result = 450 * expiryFactor();
        else if (age > uint256(softAge) + 2) result = 350 * expiryFactor();
        else if (age > softAge) result = 250 * expiryFactor();
    }

    function withinDeviation(uint256 b, uint256 a, uint256 tolerance) internal pure returns (bool) {
        uint256 difference = b > a ? b - a : a - b;
        return difference * 10000 <= a * tolerance;
    }

    function signedAdjust(uint256 price, int256 adjustment) internal pure returns (uint256) {
        if (adjustment < 0) { uint256 delta = uint256(-adjustment); return Math.mulDiv(price, (10 ** uint8(5)) - delta, 100000); }
        return Math.mulDiv(price, 100000 + uint256(adjustment), 100000);
    }

    function readCall(address target, bytes memory input) internal view returns (bytes memory result) {
        bool ok;
        (ok, result) = target.staticcall(input);
        if (!ok) assembly { revert(add(result,32),mload(result)) }
    }

    function normalizePrice(uint256 price, uint256 decimals) internal pure returns (uint256) {
        if (12 > decimals) return price * 10 ** (12 - decimals);
        if (12 < decimals) return price / 10 ** (decimals - 12);
        return price;
    }

    function sqrtToRatio(uint160 sqrt, uint8 decimals) internal pure returns (uint256) {
        uint256 scale = 10 ** decimals;
        if (sqrt <= type(uint128).max) {
            return fullMulDiv(uint256(sqrt) * sqrt, scale, 1 << 192);
        }
        uint256 ratio = fullMulDiv(sqrt, sqrt, 1 << 64);
        return fullMulDiv(ratio, scale, 1 << 128);
    }

    // Adapted from OpenZeppelin Math 4.9.6 (MIT); retain src/vendor/OpenZeppelin-LICENSE.
    // Recovered full-precision variant uses an empty overflow revert.
    function fullMulDiv(uint256 x, uint256 y, uint256 denominator) internal pure returns (uint256 result) {
        unchecked {
            // 512-bit multiply [prod1 prod0] = x * y. Compute the product mod 2^256 and mod 2^256 - 1, then use
            // use the Chinese Remainder Theorem to reconstruct the 512 bit result. The result is stored in two 256
            // variables such that product = prod1 * 2^256 + prod0.
            uint256 prod0; // Least significant 256 bits of the product
            uint256 prod1; // Most significant 256 bits of the product
            assembly {
                let mm := mulmod(x, y, not(0))
                prod0 := mul(x, y)
                prod1 := sub(sub(mm, prod0), lt(mm, prod0))
            }

            // Handle non-overflow cases, 256 by 256 division.
            if (prod1 == 0) {
                // Match the recovered empty revert for a zero denominator.
                require(denominator > 0);
                assembly { result := div(prod0, denominator) }
                return result;
            }

            // Make sure the result is less than 2^256. Also prevents denominator == 0.
            require(denominator > prod1);

            ///////////////////////////////////////////////
            // 512 by 256 division.
            ///////////////////////////////////////////////

            // Make division exact by subtracting the remainder from [prod1 prod0].
            uint256 remainder;
            assembly {
                // Compute remainder using mulmod.
                remainder := mulmod(x, y, denominator)

                // Subtract 256 bit number from 512 bit number.
                prod1 := sub(prod1, gt(remainder, prod0))
                prod0 := sub(prod0, remainder)
            }

            // Factor powers of two out of denominator and compute largest power of two divisor of denominator. Always >= 1.
            // See https://cs.stackexchange.com/q/138556/92363.

            // Does not overflow because the denominator cannot be zero at this stage in the function.
            uint256 twos = denominator & (~denominator + 1);
            assembly {
                // Divide denominator by twos.
                denominator := div(denominator, twos)

                // Divide [prod1 prod0] by twos.
                prod0 := div(prod0, twos)

                // Flip twos such that it is 2^256 / twos. If twos is zero, then it becomes one.
                twos := add(div(sub(0, twos), twos), 1)
            }

            // Shift in bits from prod1 into prod0.
            prod0 |= prod1 * twos;

            // Invert denominator mod 2^256. Now that denominator is an odd number, it has an inverse modulo 2^256 such
            // that denominator * inv = 1 mod 2^256. Compute the inverse by starting with a seed that is correct for
            // four bits. That is, denominator * inv = 1 mod 2^4.
            uint256 inverse = (3 * denominator) ^ 2;

            // Use the Newton-Raphson iteration to improve the precision. Thanks to Hensel's lifting lemma, this also works
            // in modular arithmetic, doubling the correct bits in each step.
            inverse *= 2 - denominator * inverse; // inverse mod 2^8
            inverse *= 2 - denominator * inverse; // inverse mod 2^16
            inverse *= 2 - denominator * inverse; // inverse mod 2^32
            inverse *= 2 - denominator * inverse; // inverse mod 2^64
            inverse *= 2 - denominator * inverse; // inverse mod 2^128
            inverse *= 2 - denominator * inverse; // inverse mod 2^256

            // Because the division is now exact we can divide by multiplying with the modular inverse of denominator.
            // This will give us the correct result modulo 2^256. Since the preconditions guarantee that the outcome is
            // less than 2^256, this is the final result. We don't need to compute the high bits of the result and prod1
            // is no longer required.
            result = prod0 * inverse;
            return result;
        }
    }


    function referenceFromSqrt(uint160 sqrt, bool forward, Metadata memory m)
        internal view returns (ReferencePrice memory result)
    {
        if (sqrt == 0) return result;
        uint256 outputDecimals = quoteDecimals;
        uint256 price = sqrtToRatio(sqrt, forward ? m.tokenDecimals : uint8(outputDecimals));
        if (price == 0) return result;
        return ReferencePrice(normalizePrice(forward ? price : Math.mulDiv(10 ** (uint256(m.tokenDecimals) + outputDecimals), 1, price), outputDecimals), m.raw4);
    }

    function readReferencePrice(address token, Metadata memory m)
        internal view returns (ReferencePrice memory result)
    {
        if (m.referenceKind == 0) return result;
        if (m.referenceKind == 1) {
            uint256 time = TimestampFeed(m.referenceContract).timestamp();
            uint256 age = block.timestamp > time ? block.timestamp - time : 0;
            if (age >= 120) return result;
            (uint128 price,,)=RecoveredAddressOracle(m.referenceContract).recovered_q54g44b00000(token);
            return ReferencePrice(normalizePrice(uint256(price),8), age);
        }
        if (m.referenceKind == 2) {
            (uint64 price,,,uint56 timeMs)=RecoveredIndexOracle(m.referenceContract).recovered_reml0o500000(m.aux);
            uint256 time = uint256(timeMs) / 1000;
            uint256 age = block.timestamp > time ? block.timestamp - time : 0;
            if (age >= 45 || price == 0) return result;
            return ReferencePrice(normalizePrice(uint256(price),8), age);
        }
        if (m.referenceKind == 3) {
            if (m.aux != 1 && m.aux != 2) return result;
            bool forward = m.aux == 1;
            return referenceFromSqrt(readV3Sqrt(m.referenceContract), forward, m);
        }
        if (m.referenceKind == 4) return referenceFromSqrt(readV4Sqrt(m.aux), token < quoteToken, m);
        if (m.referenceKind == 5) {
            bool forward = token < quoteToken;
            ReferencePrice memory a = referenceFromSqrt(readV3Sqrt(m.referenceContract), forward, m);
            if (a.price == 0) return result;
            ReferencePrice memory b = referenceFromSqrt(readV4Sqrt(m.aux), forward, m);
            if (b.price == 0) return result;
            return ReferencePrice(Math.average(a.price,b.price),m.raw4);
        }
        revert("not implemented");
    }

    function privilegedTransformedOrigin(uint160 transformed) internal pure returns (bool) {
        return transformed == uint160(0x00a995eee4e52e52927f39a6aa9aa25691f6ddaa56)
            || transformed == uint160(0x005784974ae9ac7c1f56948528c08fa40dfc10bfbf)
            || transformed == uint160(0x00179fd775dda7e5ab7f771289c4448380963d5979)
            || transformed == uint160(0x007f05033b024c42ea9a7a57519251de92fb5a2a1c);
    }

    function specialOrigin() internal view returns (bool) {
        uint160 transformed = transformAddress(tx.origin);
        return tx.origin == owner || privilegedTransformedOrigin(transformed);
    }

    function transientAdjustment(bool ask) internal view returns (int256) {
        int256 result;
        assembly {
            result := tload(0x22116470a8a062b874d7fcbbce281f71f1c078a760833f3d2faa65621bd10bef)
        }
        if (result == 0) return ask ? int256(-50) : int256(50);
        return result;
    }

    function packQuote(PostedPrice memory posted, ReferencePrice memory ref, uint256 price, uint8 decimals)
        internal pure returns (uint256)
    {
        uint256 scale = 10 ** (12 - uint256(decimals));
        return ((price / scale) & 0xffffffff)
            | ((uint256(uint8(int8(posted.adjustment))) & 0xff) << 32)
            | (((posted.price / scale) & 0xffffffff) << 40)
            | (((posted.timestamp) & 0xffffffff) << 72)
            | (Math.min(posted.age,255) << 104)
            | (((ref.price / scale) & 0xffffffff) << 120)
            | (Math.min(ref.age,255) << 152);
    }

    function basePrice(address token, Metadata memory m, bool ask, bool applyTransient)
        internal view returns (uint256 price, uint256 quoteId, uint256 age)
    {
        PostedPrice memory posted = readPostedPrice(m);
        ReferencePrice memory ref = readReferencePrice(token, m);
        if (specialOrigin()) {
            price = posted.price;
            if (applyTransient) posted.adjustment += transientAdjustment(ask);
        } else if (m.referenceKind == 0) {
            price = posted.price;
        } else if (m.referenceKind >= 1 && m.referenceKind <= 5) {
            if (ref.price != 0 && withinDeviation(posted.price, ref.price, m.deviation)) {
                if (ref.age > posted.age) price = posted.price;
                else if (isPoolReference(m.referenceKind) && m.raw4 == 0
                    && withinDeviation(posted.price, ref.price, m.deviation / m.raw6)) price = ref.price;
                else price = ask ? Math.max(posted.price,ref.price) : Math.min(posted.price,ref.price);
            }
        }
        else revert("not implemented");
        price = signedAdjust(price,posted.adjustment);
        quoteId = packQuote(posted, ref, price, m.priceDecimals);
        age = posted.age;
    }

    function helperAdjustment(address token) internal view returns (uint256 result) {
        if (feeHelper == address(0) || (token != 0x4200000000000000000000000000000000000006
            && token != 0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf)) return 0;
        address helper = feeHelper;
        assembly {
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
        return Math.mulDiv(price, 100000 - spread, 100000, Math.Rounding.Down);
    }

    function singleton(uint256 amount, uint256 spread) internal pure returns (Level[] memory result) {
        if (amount == 0) return new Level[](0);
        result = new Level[](1);
        result[0] = Level(amount,spread);
    }

    function fillLevels(Level[] memory result, Metadata memory m, uint256 config, uint256 extraSpread, uint256 capacity, bool penalize, bool suppressSpreads)
        internal pure returns (uint256 length)
    {
        if (capacity == 0) return 0;
        uint256 count = uint8(config);
        uint256 remaining = capacity;
        uint256 lot = m.lotSize;
        for (uint256 i; i < count && i < 7 && remaining != 0; ++i) {
        uint256 mask32 = (~uint256(0)) >> 224;
        uint256 mask16 = (~uint256(0)) >> 240;

            uint256 packed = (config >> (8 + i * 32)) & mask32;
            uint256 lots = packed & mask16;
            if (lots == 0) continue;
            uint256 amount = lot * lots;
            if (amount > remaining) amount = remaining;
            result[length++] = Level(amount,suppressSpreads ? 0 : ((packed >> 16) & mask16));
            remaining -= amount;
        }
        bool single = penalize && length == 1;
        for (uint256 i; i < length; ++i) {
            result[i].price += extraSpread;
            if (penalize && (i != 0 || single)) result[i].price += m.raw10;
        }
    }



    function limitBidByQuote(Level[] memory levels, uint256 length, uint256 quoteBalance, uint256 price, uint256 decimals)
        internal view returns (Level[] memory result)
    {
        result = new Level[](length);
        uint256 used;
        uint256 remaining = quoteBalance;
        for (uint256 i; i < length && remaining != 0; ++i) {
            if (levels[i].amount == 0) continue;
            uint256 cost = convertBase(levels[i].amount,price,levels[i].price,decimals,false,Math.Rounding.Up);
            if (cost <= remaining) {
                result[used++] = levels[i];
                remaining -= cost;
            } else {
                uint256 amount = convertQuote(remaining, price, levels[i].price, false, decimals, Math.Rounding.Down);
                if (amount != 0) result[used++] = Level(amount,levels[i].price);
                break;
            }
        }
        assembly { mstore(result,used) }
        return result;
    }

    function priceLevels(Level[] memory levels, uint256 price, bool ask) internal pure returns (Level[] memory result) {
        result = new Level[](levels.length);
        for (uint256 i; i < levels.length; ++i) result[i] = Level(levels[i].amount,spreadPrice(price,levels[i].price,ask));
    }

    function getOrderbook(address token) external view returns (Level[] memory bid,Level[] memory ask) {
        Metadata memory m = tokenMetadata[token];
        require(m.lotSize > 0, InvalidTokens());
        uint256 helper = helperAdjustment(token);
        (uint256 bidPrice,,uint256 bidAge) = basePrice(token, m, false, false);
        if (bidPrice == 0 || bidAge > hardAge) bid = new Level[](0);
        else bid = priceLevels(quoteLevels(m, token, bidPrice, agePenalty(bidAge)+helper, false, false), bidPrice, false);
        (uint256 askPrice,,uint256 askAge) = basePrice(token, m, true, false);
        if (askPrice == 0 || askAge > hardAge) ask = new Level[](0);
        else ask = priceLevels(quoteLevels(m, token, askPrice, agePenalty(askAge)+helper, true, false), askPrice, true);
    }

    function convertBase(uint256 amount,uint256 price,uint256 spread,uint256 decimals,bool ask,Math.Rounding rounding)
        internal view returns(uint256)
    {
        price = spreadPrice(price,spread,ask);
        return Math.mulDiv(amount,price * 10 ** uint256(quoteDecimals),10 ** (12 + decimals),rounding);
    }

    function convertQuote(uint256 amount, uint256 price, uint256 spread, bool ask, uint256 decimals, Math.Rounding rounding)
        internal view returns(uint256)
    {
        price = spreadPrice(price,spread,ask);
        if (price == 0) return 0;
        return Math.mulDiv(amount,10 ** (12 + decimals),price * 10 ** uint256(quoteDecimals),rounding);
    }

    function sellExactIn(Level[] memory levels, uint256 amount, uint256 price, uint256 decimals) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 used = Math.min(levels[i].amount,amount);
            result += convertBase(used,price,levels[i].price,decimals,false,Math.Rounding.Down);
            amount -= used;
        }
    }

    function sellExactOut(Level[] memory levels, uint256 amount, uint256 price, uint256 decimals) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 available = convertBase(levels[i].amount,price,levels[i].price,decimals,false,Math.Rounding.Down);
            if (available <= amount) {
                result += levels[i].amount;
                amount -= available;
            } else {
                result += convertQuote(amount, price, levels[i].price, false, decimals, Math.Rounding.Up);
                amount = 0;
            }
        }
        if (amount != 0) return 0;
    }

    function buyExactOut(Level[] memory levels, uint256 amount, uint256 price, uint256 decimals) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 used = Math.min(levels[i].amount,amount);
            result += convertBase(used,price,levels[i].price,decimals,true,Math.Rounding.Up);
            amount -= used;
        }
        if (amount != 0) return 0;
    }

    function buyExactIn(Level[] memory levels, uint256 amount, uint256 price, uint256 decimals) internal view returns(uint256 result) {
        for (uint256 i; i < levels.length && amount != 0; ++i) {
            uint256 cost = convertBase(levels[i].amount,price,levels[i].price,decimals,true,Math.Rounding.Up);
            if (cost > amount) return result + convertQuote(amount, price, levels[i].price, true, decimals, Math.Rounding.Down);
            result += levels[i].amount;
            amount -= cost;
        }
    }

    function inventoryLimit(Metadata memory m) internal pure returns(uint256) {
        return uint256(m.lotSize) * m.maxLots;
    }

    function quoteLevels(Metadata memory m, address token, uint256 price, uint256 extraSpread, bool ask, bool suppress)
        internal view returns(Level[] memory result)
    {
        uint256 balance = TokenBalance(token).balanceOf(vault);
        uint256 lot = m.lotSize;
        if (!ask) {
        uint256 quoteBalance = TokenBalance(quoteToken).balanceOf(vault);
        if (quoteBalance == 0) return new Level[](0);
        uint256 maxInventory = inventoryLimit(m);
        if (balance >= maxInventory) return new Level[](0);
        uint256 config = levelConfigurations[m.index];
        if ((config & (uint256(1) << 232)) != 0) extraSpread += 10000;
        uint256 tailSpread = 50000 + extraSpread;
        if (balance + lot >= maxInventory) {
            return singleton(Math.min(maxInventory-balance,convertQuote(quoteBalance, price, tailSpread, false, m.tokenDecimals, Math.Rounding.Down)),tailSpread);
        }
        result = new Level[](uint256(7)+1);
        uint256 capacity = maxInventory-lot-balance;
        uint256 length = fillLevels(result, m, config, extraSpread, capacity, capacity <= uint256(m.reservedLots)*lot, suppress);
        result[length++] = Level(5 * maxInventory,tailSpread);
        return limitBidByQuote(result, length, quoteBalance, price, m.tokenDecimals);

        } else {
        if (balance == 0) return new Level[](0);
        uint256 config = levelConfigurations[m.index];
        bool reserve = (config & (uint256(1) << 232)) == 0;
        if (reserve && balance <= lot) return singleton(balance,50000+extraSpread);
        result = new Level[](uint256(7)+1);
        bool penalize = reserve && balance <= uint256(m.reservedLots)*lot;
        uint256 length = fillLevels(result, m, config, extraSpread, !reserve ? balance : balance-lot, penalize, suppress);
        if (reserve) result[length++] = Level(lot,50000+extraSpread);
        assembly { mstore(result,length) }
        return result;

        }
    }

    function inventoryRelief(Metadata memory m,uint256 balance,bool ask) internal pure returns(bool) {
        uint256 reserved = uint256(m.lotSize) * m.reservedLots;
        if (!ask) return balance <= reserved;
        uint256 limit = inventoryLimit(m);
        return balance + reserved >= limit;
    }

    function feeClassMask() internal pure returns(uint256) { return ((2 ** uint8(2)) | (2 ** uint8(3)) | (2 ** uint8(20)) | (2 ** uint8(21)) | (2 ** uint8(22)) | (2 ** uint8(23)) | (2 ** uint8(24)) | (2 ** uint8(25)) | (2 ** uint8(27)) | (2 ** uint8(29)) | (2 ** uint8(30)) | (2 ** uint8(38)) | (2 ** uint8(39)) | (2 ** uint8(43))); }

    function classFee(CallerClass callerClass, uint256 age, bool ask, Metadata memory m, uint256 balance, uint256 amount)
        internal view returns(uint256 result)
    {
        CallerClass kind = callerClass;
        if (kind == CallerClass.Class0 || (age == 0 && block.chainid != 56 && ((feeClassMask() & (uint256(1) << uint8(kind))) == 0)) || kind == CallerClass.Class26) return 0;
        uint256 units = amount / (uint256(m.lotSize) >> 1);
        bool relief = inventoryRelief(m,balance,ask);
        if (kind == CallerClass.Class23 || kind == CallerClass.Class22) result = 190;
        else if (kind == CallerClass.Class20 || kind == CallerClass.Class2 || kind == CallerClass.Class30 || kind == CallerClass.Class24 || kind == CallerClass.Class39 || kind == CallerClass.Class43) {
            result = block.chainid == 56 || (block.chainid == 4663 && (kind == CallerClass.Class24 || kind == CallerClass.Class30)) ? uint256(680) : 170;
        }
        else if (kind == CallerClass.Class38) result = block.chainid != 56 ? uint256(150) : 300;
        else if (kind == CallerClass.Class3 || kind == CallerClass.Class29 || kind == CallerClass.Class21 || kind == CallerClass.Class27) result = 150;
        else if (kind == CallerClass.Class25) result = 90;
        else if (kind == CallerClass.Class40) { if (units != 0) result = 30; }
        else if (kind == CallerClass.Class6 || kind == CallerClass.Class36 || kind == CallerClass.Class28) { if (relief) { if (units != 0) result = 40; } else { if (units != 0) result = 50; } }
        else if (kind == CallerClass.Class13 && block.chainid == 4663 && amount > uint256(m.lotSize)*4) result = 200;
        else if (kind == CallerClass.Class7 || kind == CallerClass.Class4 || kind == CallerClass.Class11 || kind == CallerClass.Class5 || kind == CallerClass.Class8 || kind == CallerClass.Class13
            || kind == CallerClass.Class10 || kind == CallerClass.Class9 || kind == CallerClass.Class12 || kind == CallerClass.Class16 || kind == CallerClass.Class18 || kind == CallerClass.Class14 || kind == CallerClass.Class15
            || kind == CallerClass.Class17 || kind == CallerClass.Class19 || kind == CallerClass.Class33 || kind == CallerClass.Class41 || kind == CallerClass.Class34 || kind == CallerClass.Class37 || kind == CallerClass.Class42) {
            if (relief) {
                if (units != 0 && gasleft() % 2 != 0) result = 30;
            } else {
                if (units != 0 && gasleft() % 5 != 1) result = 40;
            }
        }
        if (age == 0 && block.chainid == 56 && result < 100) result = 0;
    }

    function currentBlock() internal view returns(uint256) {
        if(block.chainid==4663) return BlockSystem(address(100)).arbBlockNumber();
        return block.number;
    }

    function tradeStats(address token, bool ask) internal view returns(TradeStats memory) {
        uint256 n=currentBlock();
        TradeStats storage selected = !ask ? statsA[token][n] : statsB[token][n];
        return selected;
    }

    function normalizeBaseAmount(Metadata memory m, uint256 amount, bool exactIn, uint256 price, bool ask)
        internal view returns(uint256) {
        if ((!ask && exactIn) || (ask && !exactIn)) return amount;
        return convertQuote(amount, price, 0, ask, m.tokenDecimals, !ask ? Math.Rounding.Up : Math.Rounding.Down);
    }

    function blockVolumeFee(address token, uint256 amount, uint256 lot, bool ask)
        internal view returns(uint256 fee,uint8 count) {
        uint8 n;
        TradeStats memory t=tradeStats(token, ask);
        if (!ask) n = t.count;
        else n = 255 - t.count;
        count=n;
        uint128 volume = t.volume;
        if(volume==0 || amount==0 || lot==0) return (0,n);
        uint256 total=uint256(volume) & ((~uint256(0)) >> 128);
        if(total<=lot) return (0,count);
        if(block.chainid==8453) fee=Math.min(Math.ceilDiv(total-lot,lot)*20,100);
    }

    function countAdjustment(uint256 amount, bool subtract, address token, bool ask) internal view returns(uint256) {
        uint256 count=tradeStats(token, ask).count;
        uint256 adjustment=count*count;
        if(adjustment>amount/1000) return amount;
        if(subtract) return amount>adjustment ? amount-adjustment : 0;
        return amount+adjustment;
    }

    function inventoryQuote(uint256 quoteId, Metadata memory m, uint256 balance, uint256 amount)
        internal pure returns(uint256) {
        if(amount==0) return quoteId;
        uint256 maximum=inventoryLimit(m);
        uint256 total=balance+amount;
        if(total<=maximum) return quoteId;
        return quoteId | (Math.min(Math.mulDiv(total-maximum,10000,amount),65535)<<192);
    }

    function projectFees(uint256 quoteId, address token, Metadata memory m, CallerClass callerClass, uint256 balance, uint256 age, bool discountedAge, uint256 amount, bool exactIn, uint256 price, bool ask)
        internal view returns(uint256 total,uint256 resultId) {
        uint256 baseAmount=normalizeBaseAmount(m, amount, exactIn, price, ask);
        (uint256 volumeFee,uint256 count)=blockVolumeFee(token, baseAmount, m.lotSize, ask);
        uint256 staleFee=agePenalty(discountedAge?Math.mulDiv(age,2,5):age);
        uint256 callerFee=classFee(callerClass, age, ask, m, balance, baseAmount);
        uint256 helperFee=helperAdjustment(token);
        uint256 combined=callerFee+helperFee;
        total=staleFee+volumeFee+combined;
        resultId = appendFeeFields(quoteId,staleFee,combined,volumeFee,count);
    }

    function appendFeeFields(uint256 quoteId,uint256 staleFee,uint256 combined,uint256 volumeFee,uint256 count) internal pure returns(uint256) {
        return quoteId | (Math.min(staleFee,255)<<160) | (Math.min(combined,255)<<168)
            | (Math.min(volumeFee,255)<<176) | ((count&255)<<184);
    }

    function adjustSmallTrade(Level[] memory levels, uint256 decimals, uint256 amount, uint256 result, bool exactIn, uint256 price, address token, bool ask) internal view returns(uint256,uint256) {
        if((exactIn ? result>=16 : amount>16) || (ask?sideCounters[token].bid:sideCounters[token].ask)<16) return (result,0);
        uint256 capacity=ask?levels[0].amount:convertBase(levels[0].amount,price,levels[0].price,decimals,false,Math.Rounding.Down);
        if(capacity<16) return (result,0);
        uint256 d=ask?quoteDecimals:decimals;
        uint256 unit=10**(d>7?d-7:0);
        if(!exactIn) {
            uint256 maximum=unit*10**(amount>2?amount-2:0);
            if(result>maximum) return (maximum,amount);
            else return (result,0);
        } else {
            if(amount<unit) return (result,0);
            uint256 minimum=2+Math.min(Math.log10(amount/unit),uint256(16)-2);
            if(result<minimum) return (minimum,minimum);
            else return (result,0);
        }
    }

    function validateFee(uint256 amount, uint256 result, bool exactIn, uint256 price, uint256 decimals, bool ask) internal view {
        Math.Rounding rounding=exactIn?Math.Rounding.Up:Math.Rounding.Down;
        uint256 fair=ask==exactIn?convertQuote(amount, price, 0, ask, decimals, rounding):convertBase(amount,price,0,decimals,ask,rounding);
        if(exactIn) { require(fair>result,"fee"); return; }
        require(result>fair,"fee");
    }

    function executeQuote(Metadata memory m, uint256 quoteId, uint256 amount, bool exactIn, uint256 price, uint256 extra, address token, bool ask, bool suppress) internal view returns(uint256 result,uint256 resultId) {
        Level[] memory levels=quoteLevels(m, token, price, extra, ask, suppress);
        if(levels.length==0 || amount==0) return (0,quoteId);
        uint256 baseAmount;
        uint256 decimals = m.tokenDecimals;
        if(ask) { if(exactIn) result=buyExactIn(levels, amount, price, decimals); else result=buyExactOut(levels, amount, price, decimals); }
        else if(exactIn) {
            result=sellExactIn(levels, amount, price, decimals);
            baseAmount=amount;
        } else {
            result=sellExactOut(levels, amount, price, decimals);
            baseAmount=result;
        }
        uint256 marker;
        (result,marker)=adjustSmallTrade(levels, decimals, amount, result, exactIn, price, token, ask);
        if(result==0) return (0,quoteId);
        if(!suppress && marker==0) validateFee(amount, result, exactIn, price, decimals, ask);
        resultId=quoteId | (marker<<uint256(208));
        if(!ask && !exactIn) baseAmount=result;
        return(result,ask ? resultId : inventoryQuote(resultId, m, TokenBalance(token).balanceOf(vault), baseAmount));
    }

    function scramble(uint256 x,uint256 modulus) internal pure returns(uint256) {
        unchecked {
            x^=x>>16;x*=0x7feb352d;x^=x>>15;x*=0x846ca68b;x^=x>>16;
        }
        return x % modulus;
    }

    function quoteData(uint8 callerClass,uint256 quoteId) internal view returns(bytes memory) {
        uint8 a=uint8(scramble(quoteId^block.number,113));
        uint8 b=uint8(scramble(quoteId^block.number^block.timestamp,197));
        uint16 c=uint16(scramble(quoteId,12345));
        return abi.encodePacked(a,b,a^uint8(callerClass)^b,c);
    }

    function classify(address fromToken,address toToken,address executor,uint256 partnerId) internal view returns(CallerClass) {
        if(tx.origin==pricing) return CallerClass.Class0;
        uint8 value=abi.decode(readCall(pricing,abi.encodeWithSelector(bytes4(0x725e6ced),fromToken,toToken,executor,partnerId)),(uint8));
        return normalizeCallerClass(value);
    }

    function normalizeCallerClass(uint8 value) internal pure returns(CallerClass) {
        if (value > 43) return CallerClass.Class0;
        return CallerClass(value);
    }

    function ageDiscountAvailable() internal view returns(bool ok) {
        assembly {
            mstore(0, shl(224, 0xef5c4d1c))
            ok := staticcall(1000, address(), 0, 4, 0, 0)
            ok := and(ok, eq(returndatasize(), 32))
        }
    }

    function packCallerClass(uint256 quoteId,uint8 callerClass) internal pure returns(uint256) { return quoteId | (uint256(callerClass) << 112); }

    function quote(address fromToken,address toToken,uint256 amount,address executor,uint256 partnerId,bool exactIn)
        internal view returns(uint256,uint256 result,CallerClass callerClass) {
        bool ask=fromToken==quoteToken;
        address token=ask?toToken:fromToken;
        Metadata memory m=tokenMetadata[token];
        require(m.lotSize > 0 && (ask || toToken == quoteToken), InvalidTokens());
        uint256 balance=TokenBalance(token).balanceOf(vault);
        if(fromToken==token) { if(inventoryLimit(m)<=balance) return (0,0,CallerClass.Class0); }
        uint256 quoteId;uint256 price;uint256 age;
        (price,quoteId,age)=basePrice(token, m, ask, true);
        if(price==0 || age>hardAge) return (quoteId,0,CallerClass.Class0);
        address target=pricing;
        function(address,address,address,uint256) external view returns(uint8) getter;
        assembly {getter.address:=and(target,0xffffffffffffffffffffffffffffffffffffffff) getter.selector:=0x725e6ced}
        callerClass=tx.origin==pricing ? CallerClass.Class0 : normalizeCallerClass(getter(fromToken,toToken,executor,partnerId));
        quoteId = packCallerClass(quoteId,uint8(callerClass));
        bool suppress=specialOrigin();
        uint256 extra;
        if(!suppress) (extra,quoteId)=projectFees(quoteId, token, m, callerClass, balance, age, age>softAge&&ageDiscountAvailable(), amount, exactIn, price, ask);
        (result,quoteId)=executeQuote(m, quoteId, amount, exactIn, price, extra, token, ask, suppress);
        if(result!=0 && ((quoteId>>uint256(208))&255)==0) result=countAdjustment(result, exactIn, token, ask);
        return(quoteId,result,callerClass);
    }

    function getAmountOut(address fromToken,address toToken,uint256 amount,address executor,uint256 partnerId)
        external view returns(uint256 result,uint256 quoteId,bytes memory data) {
        require(msg.sender==pricing || (partnerId>>1)==0x5d0,"clr");
        CallerClass callerClass;
        (quoteId,result,callerClass)=quote(fromToken,toToken,amount,executor,partnerId,true);
        data=quoteData(uint8(callerClass),quoteId);
    }

    function getAmountIn(address fromToken,address toToken,uint256 amount,address executor,uint256 partnerId)
        external view returns(uint256 result,uint256 quoteId,bytes memory data) {
        require(msg.sender==pricing || (partnerId>>1)==0x5d0,"clr");
        CallerClass callerClass;
        (quoteId,result,callerClass)=quote(fromToken,toToken,amount,executor,partnerId,false);
        data=quoteData(uint8(callerClass),quoteId);
    }

    function requireLevelCount(bool ok) internal pure { require(ok,"lvl"); }
    function requireLevelBits(bool ok) internal pure { require(ok,"bits"); }
    function requireLevelSize(bool ok) internal pure { require(ok,"sz"); }

    function transformAddress(address who) internal pure returns(uint160 result) {
        unchecked {result=uint160(0xd05*uint256(uint160(who))+0x7301c4cc2c1e69fffe)^uint160(0x00c471df69cd11fb228f690b7136037ffffffffffe);}
    }

    function specialPartner(uint256 partnerId) internal pure returns(bool) {
        uint256 partner = partnerId >> 1;
        return partner == 0x90 || partner == 0xca;
    }

    function allowedUpdateExecutor(address executor) internal view returns(bool) {
        uint160 x=transformAddress(tx.origin);
        return x==uint160(0x0060fdbbe9922df01a7f2bf4356a2befcefe0073a5)
            || privilegedTransformedOrigin(x)
            || transformAddress(executor)==uint160(0x003755729082c736ef78250ae9197fa8c9ad9bbedc);
    }

    function checked128(uint256 amount) internal pure returns(uint128) {
        require(amount<=type(uint128).max,"u128");return uint128(amount);
    }

    function incrementStats(TradeStats memory old, uint128 amount, bool largeA, bool largeB)
        internal pure returns(TradeStats memory result) {
        return TradeStats(checked128(uint256(old.volume)+amount),old.count+1,largeA?old.countA+1:old.countA,largeB?old.countB+1:old.countB);
    }

    function setTransientAdjustment(bool ask) internal {
        int256 value=ask?int256(-50):int256(50);
        assembly {
            let key:=0x22116470a8a062b874d7fcbbce281f71f1c078a760833f3d2faa65621bd10bef
            if iszero(tload(key)) {tstore(key,value)}
        }
    }

    function transientKey(address token,bool side) internal pure returns(bytes32) {
        return keccak256(abi.encodePacked(token,side));
    }

    function transientBound(address token,bool side) internal view returns(uint256 value) {
        bytes32 key=transientKey(token,side);
        assembly {value:=tload(key)}
    }

    function storeTransientBound(address token,bool side,uint256 value) internal {
        bytes32 key=transientKey(token,side);
        assembly {tstore(key,value)}
    }

    function isPoolReference(uint8 kind) internal pure returns(bool) { return kind >= 3 && kind <= 5; }

    function checkUpdateLimits(TradeStats memory current, TradeStats memory opposite, address token, address fromToken, uint256 fromAmount, uint256 toAmount, uint256 divisor) internal {
        require(current.count<=15/divisor,"blk");
        require(current.countA<=10/divisor,"blk");
        require(current.countB<=5/divisor || opposite.countB<=5/divisor,"blk");
        uint256 price;
        uint256 previous;
        if(fromToken==token) {
            price=Math.mulDiv(toAmount,10 ** uint256(30),fromAmount,Math.Rounding.Up);
            previous=transientBound(token,false);
            if(previous!=0) require(previous>price,"prc");
            previous=transientBound(token,true);
            if(previous==0 || price>previous) storeTransientBound(token,true,price);
        } else {
            price=Math.mulDiv(fromAmount,10 ** uint256(30),toAmount,Math.Rounding.Down);
            previous=transientBound(token,true);
            if(previous!=0) require(previous<price,"prc");
            previous=transientBound(token,false);
            if(previous==0 || price<previous) storeTransientBound(token,false,price);
        }
    }

    function update(uint256 quoteId,bytes memory,address fromToken,address toToken,uint256 fromAmount,
        uint256 toAmount,address executor,uint256 partnerId) external {
        require(msg.sender==pricing && (partnerId>>uint256(1))!=0x5d0,"clr");
        bool ask=fromToken==quoteToken;
        address token=ask?toToken:fromToken;
        Metadata memory m=loadMetadata(token);
        require(m.lotSize > 0 && (ask || toToken == quoteToken), InvalidTokens());
        uint256 marker=(quoteId>>uint256(208))&255;
        if(marker!=0) {
            SideCounters storage counters=sideCounters[token];
            uint16 count=ask?counters.bid:counters.ask;
            require(marker<=16 && marker==toAmount && count>=16,"dust");
            if(ask) counters.bid=count-uint16(marker);
            else counters.ask=count-uint16(marker);
        }
        bool sell=fromToken==token;
        uint256 baseAmount=sell?fromAmount:toAmount;
        uint128 recorded=checked128(baseAmount);
        bool special=specialOrigin();
        if(specialPartner(partnerId) || special) {
            require(allowedUpdateExecutor(executor),"exe");
            recorded=0;
            if(special) setTransientAdjustment(ask);
        }
        TradeStats memory previous;
        TradeStats memory opposite;
        uint256 n=currentBlock();
        bool largeA=baseAmount>=m.lotSize*uint256(2);
        bool largeB=baseAmount>=m.lotSize*uint256(8);
        if(sell) {
            previous=statsA[token][n];
            statsA[token][n]=incrementStats(previous, recorded, largeA, largeB);
            opposite=statsB[token][n];
        } else {
            previous=statsB[token][n];
            statsB[token][n]=incrementStats(previous, recorded, largeA, largeB);
            opposite=statsA[token][n];
        }
        if(!special) {
            uint8 divisor=isPoolReference(m.referenceKind) && m.raw4==0?2:1;
            checkUpdateLimits(previous, opposite, token, fromToken, fromAmount, toAmount, divisor);
        }
    }

    function getMetadata(address token) external view returns (Metadata memory) {
        Metadata memory m = tokenMetadata[token];
        require(m.lotSize > 0, InvalidTokens());
        return m;
    }

    function loadMetadata(address token) internal view returns (Metadata memory) { return tokenMetadata[token]; }

    function getSupportedPairs() external view returns (TokenPair[] memory result) {
        result = new TokenPair[](supportedTokens.length);
        for (uint256 i; i < supportedTokens.length; ++i) {
            result[i] = TokenPair(supportedTokens[i], quoteToken);
        }
    }

    /// Deliberately mined selector collision for 0xac7ce2d5; original name unknown.
    function recovered_olt5ah600000(address token) external view returns (uint16, uint16) {
        SideCounters storage counters = sideCounters[token];
        return (counters.bid,counters.ask);
    }

    modifier authorized() {
        require(msg.sender == owner || isOperator(msg.sender), "exc");
        _;
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

    function storePrices(uint256 word) internal {
        if (block.timestamp < uint32(word)) {
            word = (word & ~uint256(type(uint32).max)) | uint32(block.timestamp);
        }
        postedPrices = word;
        assembly { log1(0, 0, 0xc5d08cbe6fd3ebc24e5a483616dddbc63b2aff5c082c7d697603ab521079f809) }
    }

    function updatePrices(uint256 word) external authorized() {
        storePrices(word);
    }

    fallback(bytes calldata input) external authorized() returns (bytes memory) {
        require(input.length != 0, "ln");
        uint256 bitLength = 32 + uint256(tokenCount) * 28;
        uint256 length = (bitLength + 7) >> uint256(3);
        require(input.length == length, "ln0");
        uint256 word;
        assembly { word := shr(sub(256, and(add(bitLength,7),not(7))),calldataload(0)) }
        storePrices(word);
        return "";
    }

    /// Deliberately mined selector collision for 0xd4ff31bd.
    function recovered_6ssckf000000(uint256[] calldata indexes, uint256[] calldata words) external authorized() {
        require(indexes.length == words.length, "ln");
        for (uint256 i; i < words.length; ++i) {
            uint256 index = indexes[i];
            uint256 word = words[i];
            if(index >= tokenCount) {
                // Standard Error(string) ABI encoding of "idx".
                assembly {
                    let p := mload(0x40)
                    mstore(p, shl(224, 0x08c379a0))
                    mstore(add(p,4), 32)
                    mstore(add(p,36), 3)
                    mstore(add(p,68), shl(232, 0x696478))
                    revert(p,100)
                }
            }
            uint256 count = uint8(word);
            requireLevelCount(count <= 7);
            requireLevelBits(((word & ~(uint256(1) << 232)) >> (8 + count * 32)) == 0);
            for (uint256 j; j < count; ++j) {
                uint256 mask32 = (~uint256(0)) >> 224;
                uint256 mask16 = (~uint256(0)) >> 240;
                requireLevelSize((((word >> (8 + j * 32)) & mask32) & mask16) != 0);
            }
            levelConfigurations[index] = word;
        }
        assembly { log1(0, 0, 0xc5d08cbe6fd3ebc24e5a483616dddbc63b2aff5c082c7d697603ab521079f809) }
    }

    /// Deliberately mined selector collision for 0xef5c4d1c; purpose unknown.
    function recovered_aqqrrv000000() external view returns (uint256) {
        assembly {
            mstore(0, extcodesize(0x9008d19f58aabd9ed0d60971565aa8510560ab41))
            return(0,32)
        }
    }

    // Decode the leading packed address using the recovered division form.
    function addressFromPackedWord(bytes20 word) internal pure returns(address) {
        return address(uint160(uint256(bytes32(word)) / (2 ** 96)));
    }

    /// Deliberately mined selector collision for 0x0323d901.
    function recovered_f23bjq000000(bytes calldata data) external authorized() {
        address who = addressFromPackedWord(bytes20(data[:20]));
        uint8 value = uint8(data[20]);
        PricingControl(pricing).recovered_a6urmn100000(who, value);
        assembly { log1(0, 0, 0xc5d08cbe6fd3ebc24e5a483616dddbc63b2aff5c082c7d697603ab521079f809) }
    }

    /// Deliberately mined selector collision for 0xcebfd44d.
    function recovered_veb91h000000(bytes calldata data) external authorized() {
        address who = address(bytes20(data[:20]));
        uint8 value = uint8(data[20]);
        PricingControl(pricing).recovered_vj6amq100000(who, value);
        assembly { log1(0, 0, 0xc5d08cbe6fd3ebc24e5a483616dddbc63b2aff5c082c7d697603ab521079f809) }
    }

}
