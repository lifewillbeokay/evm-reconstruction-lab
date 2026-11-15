// SPDX-License-Identifier: UNLICENSED
// Test-only access to reconstructed internal functions.
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
}
