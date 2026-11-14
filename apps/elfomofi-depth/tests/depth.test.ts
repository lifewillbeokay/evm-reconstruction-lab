import test from 'node:test';
import assert from 'node:assert/strict';
import {parseUnits,word,decodeBook,quoteCall,quoteResult,marginalLevels,depthAt,samplingSizes,MARKETS,DEFAULT_EXECUTOR} from '../lib/elfomo.ts';
const result=(n:bigint)=>({result:'0x'+word(n)+word(99)+word(96)+word(0)});
test('ABI and decimal scaling preserve 18- and 8-decimal token quantities',()=>{
  assert.equal(parseUnits('0.600000000000000001',18),600000000000000001n);
  assert.equal(parseUnits('0.02',8),2000000n);
  assert.throws(()=>parseUnits('0.000000001',8));assert.throws(()=>parseUnits('0',18));assert.throws(()=>parseUnits('1e18',18));
  // One WETH bid at 1762.414751 and one ask at 1762.485249.
  const raw='0x'+[64n,160n,1n,600000000000000000n,1762414751000000n,1n,600000000000000000n,1762485249000000n].map(word).join('');
  const [bid,ask]=decodeBook(raw,18);
  assert.equal(bid[0].quantity,.6);assert.equal(bid[0].price,1762.414751);assert.equal(ask[0].price,1762.485249);
  assert.throws(()=>decodeBook(raw.slice(0,-20),18));
});
test('sell and buy calls use opposite token directions with the same base amount',()=>{
  const amount=10n**18n;
  const sell=quoteCall(MARKETS[0],amount,false,DEFAULT_EXECUTOR,'7');
  const buy=quoteCall(MARKETS[0],amount,true,DEFAULT_EXECUTOR,'7');
  assert.equal(sell.slice(0,10),'0x561fa97d');assert.equal(buy.slice(0,10),'0x6486c4ac');
  assert.equal(sell.slice(10,74),buy.slice(74,138));assert.equal(sell.slice(74,138),buy.slice(10,74));
  assert.equal(sell.slice(138,202),word(amount));assert.equal(buy.slice(138,202),word(amount));
});
test('marginal depth uses quote differences, not cumulative average execution price',()=>{
  // Sell first unit for 100, second unit for 90: second marginal price is 90,
  // even though the 2-unit average execution price is 95.
  const q=[quoteResult(10n**18n,18,result(100000000n)),quoteResult(2n*10n**18n,18,result(190000000n))];
  const levels=marginalLevels(q,18);
  assert.equal(q[1].average,95);assert.equal(levels[1].price,90);
  assert.equal(depthAt(levels,'bid',100,500),100);
  assert.equal(depthAt(levels,'bid',100,1100),190);
});
test('zero quotes, RPC failures and capped output never create phantom depth',()=>{
  const ok=quoteResult(10n**18n,18,result(100000000n));
  for(const next of [quoteResult(2n*10n**18n,18,result(0n)),quoteResult(2n*10n**18n,18,{error:{message:'timeout'}}),quoteResult(2n*10n**18n,18,result(100000000n))]){
    const later=quoteResult(3n*10n**18n,18,result(250000000n));
    assert.equal(marginalLevels([ok,next,later],18).length,1);
  }
});
test('depth thresholds preserve executable prefix across non-monotonic intervals',()=>{
  const q=[100000000n,180000000n,290000000n].map((n,i)=>quoteResult(BigInt(i+1)*10n**18n,18,result(n)));
  const levels=marginalLevels(q,18);
  assert.equal(depthAt(levels,'bid',100,1000),100); // cannot skip the $80 interval to reach $110
});
test('sampling covers both ladder boundaries and the exact custom amount',()=>{
  const raw='0x'+[64n,160n,1n,600000000000000000n,1762414751000000n,0n].map(word).join('');
  const sizes=samplingSizes(MARKETS[0],decodeBook(raw,18),'1.234567890123456789');
  assert(sizes.includes(600000000000000000n));assert(sizes.includes(1234567890123456789n));
  assert(sizes.every((n,i)=>i===0||n>sizes[i-1]));
});
