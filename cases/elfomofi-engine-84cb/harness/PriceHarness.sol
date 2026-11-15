pragma solidity 0.8.34;
import "../src/EngineState.sol";
contract PriceHarness is EngineState {
    constructor(address a,address b,address c,address d,address[] memory e,Metadata[] memory f,uint8 g,uint8 h,uint8 i)
        EngineState(a,b,c,d,e,f,g,h,i) {}
    function posted(Metadata memory m) external view returns (PostedPrice memory) { return readPostedPrice(m); }
    function referencePrice(Metadata memory m,address token) external view returns (ReferencePrice memory) {return readReferencePrice(m,token);}
    function age(uint256 n) external view returns (uint256) {return agePenalty(n);}
    function adjust(int256 a,uint256 price) external pure returns (uint256) {return signedAdjust(price,a);}
    function deviation(uint256 t,uint256 a,uint256 b) external pure returns (bool) {return withinDeviation(a,b,t);}
    function sqrtPrice(uint160 s,uint8 d) external pure returns (uint256) {return sqrtToRatio(s,d);}
    function fromSqrt(Metadata memory m,uint160 s,bool forward) external view returns (ReferencePrice memory) {return referenceFromSqrt(m,s,forward);}
    function base(Metadata memory m,address token,bool ask,bool applyTransient) external view returns (uint256,uint256,uint256) {return basePrice(m,token,ask,applyTransient);}
    function pack(uint8 d,uint256 price,ReferencePrice memory r,PostedPrice memory p) external pure returns(uint256) {return packQuote(d,price,r,p);}
    function special() external view returns(bool) {return specialOrigin();}
    function bids(uint256 extra,uint256 price,address token,Metadata memory m) external view returns(Level[] memory) {return bidLevels(extra,price,token,m);}
    function asks(uint256 extra,uint256 price,address token,Metadata memory m) external view returns(Level[] memory) {return askLevels(extra,price,token,m);}
    function sellIn(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return sellExactIn(d,p,a,l);}
    function sellOut(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return sellExactOut(d,p,a,l);}
    function buyIn(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return buyExactIn(d,p,a,l);}
    function buyOut(uint8 d,uint256 p,uint256 a,Level[] memory l) external view returns(uint256) {return buyExactOut(d,p,a,l);}
    function quoteBook(bool suppress,bool ask,uint256 extra,uint256 price,address token,Metadata memory m) external view returns(Level[] memory) {return quoteLevels(suppress,ask,extra,price,token,m);}
    function feeClass(uint256 amount,uint256 balance,Metadata memory m,bool ask,uint256 age,uint256 kind) external view returns(uint256) {return classFee(amount,balance,m,ask,age,CallerClass(kind));}
    function normalize(bool ask,uint256 price,bool exactIn,uint256 amount,Metadata memory m) external view returns(uint256) {return normalizeBaseAmount(ask,price,exactIn,amount,m);}
    function volumeFee(bool ask,uint128 lot,uint256 amount,address token) external view returns(uint256,uint256) {return blockVolumeFee(ask,lot,amount,token);}
    function countAdjust(bool ask,address token,bool subtract,uint256 amount) external view returns(uint256) {return countAdjustment(ask,token,subtract,amount);}
    function inventory(uint256 amount,uint256 balance,Metadata memory m,uint256 id) external pure returns(uint256) {return inventoryQuote(amount,balance,m,id);}
    function projection(bool ask,uint256 price,bool exactIn,uint256 amount,bool discountedAge,uint256 age,uint256 balance,uint256 callerClass,Metadata memory m,address token,uint256 id) external view returns(uint256,uint256) {return projectFees(ask,price,exactIn,amount,discountedAge,age,balance,CallerClass(callerClass),m,token,id);}
    function smallTrade(bool ask,address token,uint256 price,bool exactIn,uint256 result,uint256 amount,uint8 decimals,Level[] memory levels) external view returns(uint256,uint256) {return adjustSmallTrade(ask,token,price,exactIn,result,amount,decimals,levels);}
    function feeCheck(bool ask,uint8 decimals,uint256 price,bool exactIn,uint256 result,uint256 amount) external view {validateFee(ask,decimals,price,exactIn,result,amount);}
    function execute(bool suppress,bool ask,address token,uint256 extra,uint256 price,bool exactIn,uint256 amount,uint256 id,Metadata memory m) external view returns(uint256,uint256) {return executeQuote(suppress,ask,token,extra,price,exactIn,amount,id,m);}
}
