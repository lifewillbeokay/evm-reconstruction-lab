pragma solidity 0.8.34;
import "../src/EngineState.sol";
contract PriceHarness is EngineState {
    constructor(address a,address b,address c,address d,address[] memory e,Metadata[] memory f,uint8 g,uint8 h,uint8 i)
        EngineState(a,b,c,d,e,f,g,h,i) {}
    function posted(Metadata memory m) external view returns (PostedPrice memory) { return readPostedPrice(m); }
    function referencePrice(Metadata memory m,address token) external view returns (ReferencePrice memory) {return readReferencePrice(token, m);}
    function age(uint256 n) external view returns (uint256) {return agePenalty(n);}
    function adjust(int256 a,uint256 price) external pure returns (uint256) {return signedAdjust(price,a);}
    function deviation(uint256 t,uint256 a,uint256 b) external pure returns (bool) {return withinDeviation(b, a, t);}
    function sqrtPrice(uint160 s,uint8 d) external pure returns (uint256) {return sqrtToRatio(s,d);}
    function fromSqrt(Metadata memory m,uint160 s,bool forward) external view returns (ReferencePrice memory) {return referenceFromSqrt(s, forward, m);}
    function base(Metadata memory m,address token,bool ask,bool applyTransient) external view returns (uint256,uint256,uint256) {return basePrice(token, m, ask, applyTransient);}
    function pack(uint8 d,uint256 price,ReferencePrice memory r,PostedPrice memory p) external pure returns(uint256) {return packQuote(p, r, price, d);}
    function special() external view returns(bool) {return specialOrigin();}
    function bids(uint256 extra,uint256 price,address token,Metadata memory m) external view returns(Level[] memory) {return quoteLevels(m, token, price, extra, false, false);}
    function asks(uint256 extra,uint256 price,address token,Metadata memory m) external view returns(Level[] memory) {return quoteLevels(m, token, price, extra, true, false);}
    function sellIn(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return sellExactIn(l, a, p, d);}
    function sellOut(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return sellExactOut(l, a, p, d);}
    function buyIn(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return buyExactIn(l, a, p, d);}
    function buyOut(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return buyExactOut(l, a, p, d);}
    function quoteBook(bool suppress,bool ask,uint256 extra,uint256 price,address token,Metadata memory m) external view returns(Level[] memory) {return quoteLevels(m, token, price, extra, ask, suppress);}
    function feeClass(uint256 amount,uint256 balance,Metadata memory m,bool ask,uint256 age,uint256 kind) external view returns(uint256) {return classFee(CallerClass(kind), age, ask, m, balance, amount);}
    function normalize(bool ask,uint256 price,bool exactIn,uint256 amount,Metadata memory m) external view returns(uint256) {return normalizeBaseAmount(m, amount, exactIn, price, ask);}
    function volumeFee(bool ask,uint128 lot,uint256 amount,address token) external view returns(uint256,uint256) {return blockVolumeFee(token, amount, lot, ask);}
    function countAdjust(bool ask,address token,bool subtract,uint256 amount) external view returns(uint256) {return countAdjustment(amount, subtract, token, ask);}
    function inventory(uint256 amount,uint256 balance,Metadata memory m,uint256 id) external pure returns(uint256) {return inventoryQuote(id, m, balance, amount);}
    function projection(bool ask,uint256 price,bool exactIn,uint256 amount,bool discountedAge,uint256 age,uint256 balance,uint256 callerClass,Metadata memory m,address token,uint256 id) external view returns(uint256,uint256) {return projectFees(id, token, m, CallerClass(callerClass), balance, age, discountedAge, amount, exactIn, price, ask);}
    function smallTrade(bool ask,address token,uint256 price,bool exactIn,uint256 result,uint256 amount,uint8 decimals,Level[] memory levels) external view returns(uint256,uint256) {return adjustSmallTrade(levels, decimals, amount, result, exactIn, price, token, ask);}
    function feeCheck(bool ask,uint8 decimals,uint256 price,bool exactIn,uint256 result,uint256 amount) external view {validateFee(amount, result, exactIn, price, decimals, ask);}
    function execute(bool suppress,bool ask,address token,uint256 extra,uint256 price,bool exactIn,uint256 amount,uint256 id,Metadata memory m) external view returns(uint256,uint256) {return executeQuote(m, id, amount, exactIn, price, extra, token, ask, suppress);}
}
