import test from 'node:test';
import assert from 'node:assert/strict';
import code from './fixtures/verified-code.json' with {type:'json'};
import {word,PROXY,SWAP,MARKETS,IMPLEMENTATION_SLOT} from '../lib/elfomo.ts';
import {hashHex,statsSlot,decodeStats,packStats,validateScenario,scenarioOverrides,decodeSimulation,simulate,defaultScenario,ENGINE_HASH,HELPER_HASH,VERIFIED_ENGINE,VERIFIED_HELPER,VERIFIED_IMPLEMENTATION} from '../lib/simulation.ts';
import type {Snapshot} from '../lib/simulation.ts';
const blockHash='0x'+'ab'.repeat(32);
function response(status:number,quote=18276634n,id=0n){const data=status===3?'08c379a0'+word(32)+word(3)+'626c6b'.padEnd(64,'0'):'';return '0x'+[quote,id,status,192,100000,0,data.length/2].map(word).join('')+data.padEnd(Math.ceil(data.length/64)*64,'0');}

test('verified code fingerprints and independently captured nested mapping slot',()=>{
  assert.equal(hashHex(code.engineCode),ENGINE_HASH);assert.equal(hashHex(code.helperCode),HELPER_HASH);
  assert.equal(statsSlot(MARKETS[0].address,57962726,false),'0x7c56cbc1d409d1614c3114b29b9473f13e07b50dc64be2b3925ce7f3f202935d');
  const stats={volumeRaw:'123456789012345678901',count:16,large:11,veryLarge:6};assert.deepEqual(decodeStats(packStats(stats)),stats);
});
test('decoder keeps blocked quotes distinct from successful fills and preserves fee caps',()=>{
  const id=255n<<160n|170n<<168n|20n<<176n;
  const blocked=decodeSimulation(response(3,1234n,id),'1',18,false);
  assert.equal(blocked.status,'guard-reverted');assert.equal(blocked.quoteRaw,'1234');assert.equal(blocked.reason,'blk');assert.deepEqual(blocked.fees,{stale:255,callerAndPool:170,volume:20});
  assert.equal(decodeSimulation(response(1,0n),'1',18,true).status,'no-quote');
  assert.throws(()=>decodeSimulation('0x1234','1',18,false),/Truncated/);
  assert.throws(()=>decodeSimulation(response(9),'1',18,false),/Invalid/);
});
test('scenario validation and exact overrides preserve prices, code and unrelated counters',()=>{
  const base=defaultScenario('WETH');assert.throws(()=>validateScenario({...base,callerClass:44}),RangeError);assert.throws(()=>validateScenario({...base,sizes:['0']}));assert.throws(()=>validateScenario({...base,gas:1}),RangeError);
  assert.throws(()=>validateScenario({...base,flow:{count:1,large:2,veryLarge:0,volumeLots:'1',oppositeVeryLarge:0}}),RangeError);
  const snapshot={timestamp:4096,postedWord:'0x123456789000000fff',lotRaw:'600000000000000000',sellSlot:'0x'+word(100),buySlot:'0x'+word(101),sellWord:packStats({volumeRaw:'100',count:2,large:1,veryLarge:0}),buyWord:packStats({volumeRaw:'200',count:4,large:2,veryLarge:1})} as Snapshot;
  const s={...base,age:11,flow:{count:16,large:2,veryLarge:1,volumeLots:'2.5',oppositeVeryLarge:6}};
  const overrides=scenarioOverrides(snapshot,s,false),engineOverride=overrides[VERIFIED_ENGINE];assert(engineOverride);const diff=engineOverride.stateDiff;
  assert.equal(BigInt(diff['0x'+word(2)])>>32n,BigInt(snapshot.postedWord)>>32n);assert.equal(BigInt(diff['0x'+word(2)])&0xffffffffn,4085n);
  assert.deepEqual(decodeStats(diff[snapshot.sellSlot]),{volumeRaw:'1500000000000000000',count:16,large:2,veryLarge:1});assert.equal(decodeStats(diff[snapshot.buySlot]).volumeRaw,'200');assert.equal(decodeStats(diff[snapshot.buySlot]).veryLarge,6);
  assert(!('code' in engineOverride));assert(overrides[PROXY].code.length>100);
  assert.deepEqual(Object.keys(scenarioOverrides(snapshot,base,false)),[PROXY]);
});
test('RPC simulation pins state, uses the original engine, fails closed and detects reorgs',async()=>{
  const original=globalThis.fetch;const seen:any[]=[];let wrongRoute=false,wrongCode=false,reorg=false,number=1001;
  globalThis.fetch=async(_url:any,init:any)=>Response.json(JSON.parse(init.body).map((r:any)=>{
    seen.push(r);let result:any;
    if(r.method==='eth_chainId')result='0x2105';
    else if(r.method==='eth_getBlockByNumber')result={number:'0x'+number.toString(16),hash:reorg&&r.params[0]!=='latest'?'0x'+'cd'.repeat(32):blockHash,timestamp:'0x1000'};
    else if(r.method==='eth_getCode')result=wrongCode?'0x00':r.params[0]===VERIFIED_HELPER?code.helperCode:code.engineCode;
    else if(r.method==='eth_getStorageAt')result='0x'+word(r.params[0]===PROXY?(r.params[1]===IMPLEMENTATION_SLOT?VERIFIED_IMPLEMENTATION:wrongRoute?'0x1234':VERIFIED_ENGINE):r.params[1]==='0x2'?'0xfff':0);
    else if(r.method==='eth_call'&&r.params[0].data.startsWith('0x2a50c146'))result='0x'+[0,18,4,3,1,100,1,600000000000000000n,150,5,0,PROXY,1].map(word).join('');
    else if(r.method==='eth_call')result=response(3,18276634n);
    return {id:r.id,result};
  }));
  try{
    const result=await simulate({...defaultScenario('WETH'),sizes:['0.01'],callerClass:2,age:7});
    assert.equal(result.rows.length,2);assert(result.rows.every(r=>r.status==='guard-reverted'));assert.equal(result.snapshot.postedAge,1);
    const calls=seen.filter(r=>r.method==='eth_call'&&r.params.length===3);assert.equal(calls.length,2);
    for(const c of calls){assert.equal(c.params[1],'0x3e9');assert.equal(c.params[0].to,PROXY);assert.equal(c.params[0].from,SWAP);assert(!c.params[2][VERIFIED_ENGINE].code);assert(c.params[2][PROXY].code);}
    assert(!seen.some(r=>r.method.startsWith('eth_send')));
    number++;wrongRoute=true;await assert.rejects(simulate({...defaultScenario('WETH'),sizes:['1']}),/route changed/);wrongRoute=false;
    number++;wrongCode=true;await assert.rejects(simulate({...defaultScenario('WETH'),sizes:['1']}),/bytecode differs/);wrongCode=false;
    number++;reorg=true;await assert.rejects(simulate({...defaultScenario('WETH'),sizes:['1']}),/reorganized/);
  }finally{globalThis.fetch=original;}
});
