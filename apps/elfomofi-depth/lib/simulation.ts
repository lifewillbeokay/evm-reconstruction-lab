import {keccak_256} from '@noble/hashes/sha3.js';
import {bytesToHex,hexToBytes} from '@noble/hashes/utils.js';
import probe from './execution-probe.json' with {type:'json'};
import {PROXY,SWAP,USDC,MARKETS,DEFAULT_EXECUTOR,IMPLEMENTATION_SLOT,word,uintAt,addressAt,parseUnits} from './elfomo.ts';
import type {Market} from './elfomo.ts';
import {batch,requireResult,PROVIDERS} from './rpc.ts';
import type {Request} from './rpc.ts';

export const VERIFIED_ENGINE='0x84cb1a96e57e9b88cf75035384c06dc3769654ae';
export const ENGINE_HASH='0xdd4089704d81944a7e762909aaabe5c25205848b3290e812971101ee8f881be9';
export const VERIFIED_IMPLEMENTATION='0x555a998a43a63d67abfb186b375d8aa56c66790b';
export const VERIFIED_HELPER='0x42e88fbc20c66bfe4bac17892980b640990d8cbc';
export const HELPER_HASH='0x4134563410f4611a3c10e238f4d202539afff270b4eddc8ed67c030ee36ea14b';
export type Flow={count:number;large:number;veryLarge:number;volumeLots:string;oppositeVeryLarge:number};
export type Scenario={market:string;callerClass:number;sizes:string[];age:number|null;flow:Flow|null;warmRoute:boolean;gas:number;executor:string;block?:number};
export type Stats={volumeRaw:string;count:number;large:number;veryLarge:number};
export type Snapshot={market:string;decimals:number;token:string;block:number;hash:string;timestamp:number;endpoint:string;postedWord:string;postedAge:number;lotRaw:string;inventoryLimitRaw:string;divisor:number;sellSlot:string;buySlot:string;sellWord:string;buyWord:string;sellStats:Stats;buyStats:Stats;engineHash:string;helperHash:string};
export type SimulationRow={size:string;amountRaw:string;buy:boolean;quoteRaw:string;quoteId:string;status:'passes'|'no-quote'|'quote-reverted'|'guard-reverted'|'rpc-error';reason:string;gasUsed:number;warmCodeSize:number;fees:{stale:number;callerAndPool:number;volume:number}};
export type Simulation={snapshot:Snapshot;scenario:Scenario;rows:SimulationRow[];effectiveAge:number;createdAt:number;scope:string;probeSourceSha256:string};
const snapshots=new Map<string,Promise<Snapshot>>();
export const hashHex=(hex:string)=>'0x'+bytesToHex(keccak_256(hexToBytes(hex.replace(/^0x/,''))));
export function statsSlot(token:string,block:number,buy:boolean){return hashHex(word(block)+hashHex(word(token)+word(buy?4:3)).slice(2));}
export function decodeStats(hex:string):Stats{const n=BigInt(hex);return {volumeRaw:(n&((1n<<128n)-1n)).toString(),count:Number(n>>128n&255n),large:Number(n>>136n&255n),veryLarge:Number(n>>144n&255n)};}
export function packStats(s:Stats):string{return '0x'+word(BigInt(s.volumeRaw)|(BigInt(s.count)<<128n)|(BigInt(s.large)<<136n)|(BigInt(s.veryLarge)<<144n));}
export function validateScenario(s:Scenario):Market{
  if(!s||typeof s!=='object')throw new RangeError('Invalid scenario.');
  const market=MARKETS.find(m=>m.symbol===s.market);if(!market)throw new RangeError('Choose a supported market.');
  if(!Number.isInteger(s.callerClass)||s.callerClass<0||s.callerClass>43)throw new RangeError('Caller class must be 0–43.');
  if(!Array.isArray(s.sizes)||!s.sizes.length||s.sizes.length>16)throw new RangeError('Enter 1–16 order sizes.');
  s.sizes.forEach(x=>{if(typeof x!=='string')throw new RangeError('Order sizes must be decimal strings.');parseUnits(x,market.decimals);});
  if(s.age!==null&&(!Number.isInteger(s.age)||s.age<0||s.age>120))throw new RangeError('Price age must be 0–120 seconds.');
  if(!Number.isInteger(s.gas)||s.gas<500000||s.gas>30000000)throw new RangeError('Simulation gas must be 500,000–30,000,000.');
  if(!/^0x[0-9a-f]{40}$/i.test(s.executor))throw new RangeError('Invalid executor address.');
  if(typeof s.warmRoute!=='boolean')throw new RangeError('Invalid fee context.');
  if(s.block!==undefined&&(!Number.isSafeInteger(s.block)||s.block<1))throw new RangeError('Invalid block.');
  if(s.flow){const f=s.flow;for(const n of [f.count,f.large,f.veryLarge,f.oppositeVeryLarge])if(!Number.isInteger(n)||n<0||n>255)throw new RangeError('Trade counts must be 0–255.');
    if(f.veryLarge>f.large||f.large>f.count)throw new RangeError('Large-trade counts cannot exceed total trades.');
    if(!/^\d{1,8}(\.\d{1,6})?$/.test(f.volumeLots))throw new RangeError('Volume must be a nonnegative number of lots, with up to 6 decimals.');
  }
  return market;
}
export function lotsRaw(value:string,lot:bigint):bigint{const [a,b='']=value.split('.');return lot*(BigInt(a)*1000000n+BigInt(b.padEnd(6,'0')))/1000000n;}
export function scenarioOverrides(snapshot:Snapshot,s:Scenario,buy:boolean){
  const stateDiff:Record<string,string>={};
  if(s.age!==null){if(s.age>snapshot.timestamp)throw Error('Age predates the chain timestamp.');const old=BigInt(snapshot.postedWord);stateDiff['0x'+word(2)]='0x'+word((old&~0xffffffffn)|BigInt(snapshot.timestamp-s.age));}
  if(s.flow){const f=s.flow,volume=lotsRaw(f.volumeLots,BigInt(snapshot.lotRaw));if(volume>=1n<<128n)throw new RangeError('Volume exceeds the engine uint128 counter.');
    stateDiff[buy?snapshot.buySlot:snapshot.sellSlot]=packStats({volumeRaw:volume.toString(),count:f.count,large:f.large,veryLarge:f.veryLarge});
    const opposite=BigInt(buy?snapshot.sellWord:snapshot.buyWord);stateDiff[buy?snapshot.sellSlot:snapshot.buySlot]='0x'+word((opposite&~(255n<<144n))|(BigInt(f.oppositeVeryLarge)<<144n));
  }
  return {[PROXY]:{code:probe.runtime},...(Object.keys(stateDiff).length?{[VERIFIED_ENGINE]:{stateDiff}}:{})};
}
export function simulationCall(snapshot:Snapshot,s:Scenario,size:string,buy:boolean):Request{
  return {method:'eth_call',params:[{to:PROXY,from:SWAP,data:probe.selector+[snapshot.token,parseUnits(size,snapshot.decimals),buy?1:0,s.callerClass,s.executor,s.warmRoute?1:0].map(word).join(''),gas:'0x'+s.gas.toString(16),gasPrice:'0x1'},'0x'+snapshot.block.toString(16),scenarioOverrides(snapshot,s,buy)]};
}
export function decodeReason(hex:string):string{
  try{if(hex.startsWith('0x08c379a0')){const body='0x'+hex.slice(10),offset=Number(uintAt(body,0)),length=Number(uintAt(body,offset/32));return new TextDecoder().decode(hexToBytes(body.slice(2+(offset+32)*2,2+(offset+32+length)*2)));}
    if(hex.startsWith('0x4e487b71'))return 'Solidity panic 0x'+uintAt('0x'+hex.slice(10),0).toString(16);
  }catch{/* preserve the raw revert selector below */}
  return hex==='0x'?'Empty revert data':hex.slice(0,74);
}
export function decodeSimulation(hex:string,size:string,decimals:number,buy:boolean):SimulationRow{
  const quote=uintAt(hex,0),id=uintAt(hex,1),status=Number(uintAt(hex,2)),offset=Number(uintAt(hex,3));
  if(status>3||offset%32!==0||offset<192)throw Error('Invalid simulation response.');
  const length=Number(uintAt(hex,offset/32));if(!Number.isSafeInteger(length)||2+(offset+32+length)*2>hex.length)throw Error('Truncated simulation revert data.');
  const reason='0x'+hex.slice(2+(offset+32)*2,2+(offset+32+length)*2);
  return {size,amountRaw:parseUnits(size,decimals).toString(),buy,quoteRaw:quote.toString(),quoteId:id.toString(),status:(['passes','no-quote','quote-reverted','guard-reverted'] as const)[status],reason:status>1?decodeReason(reason):status===1?'No quote: stale, unavailable reference, inventory or depth.':'Quote and engine update succeeded.',gasUsed:Number(uintAt(hex,4)),warmCodeSize:Number(uintAt(hex,5)),fees:{stale:Number(id>>160n&255n),callerAndPool:Number(id>>168n&255n),volume:Number(id>>176n&255n)}};
}
async function capture(endpoint:string,market:Market,number?:number):Promise<Snapshot>{
  const first=await batch(endpoint,[{method:'eth_chainId',params:[]},{method:'eth_getBlockByNumber',params:[number?'0x'+number.toString(16):'latest',false]}]);
  if(requireResult(first[0])!=='0x2105')throw Error('RPC is not Base.');const block=requireResult(first[1]);if(!block?.hash||!block.number||!block.timestamp)throw Error('Block unavailable.');
  const n=parseInt(block.number,16),tag=block.number,sellSlot=statsSlot(market.address,n,false),buySlot=statsSlot(market.address,n,true);
  const r=await batch(endpoint,[
    {method:'eth_getStorageAt',params:[PROXY,market.slot,tag]}, {method:'eth_getStorageAt',params:[PROXY,IMPLEMENTATION_SLOT,tag]},
    {method:'eth_getCode',params:[VERIFIED_ENGINE,tag]}, {method:'eth_getCode',params:[VERIFIED_HELPER,tag]},
    {method:'eth_getStorageAt',params:[VERIFIED_ENGINE,'0x2',tag]},
    {method:'eth_getStorageAt',params:[VERIFIED_ENGINE,sellSlot,tag]}, {method:'eth_getStorageAt',params:[VERIFIED_ENGINE,buySlot,tag]},
    {method:'eth_call',params:[{to:VERIFIED_ENGINE,data:'0x2a50c146'+word(market.address)},tag]},
  ]);
  if(addressAt(requireResult(r[0]))!==VERIFIED_ENGINE||addressAt(requireResult(r[1]))!==VERIFIED_IMPLEMENTATION)throw Error('The pricing route changed. Simulation is paused until this engine is reviewed.');
  const engineHash=hashHex(requireResult(r[2])),helperHash=hashHex(requireResult(r[3]));
  if(engineHash!==ENGINE_HASH||helperHash!==HELPER_HASH)throw Error('Engine or fee-helper bytecode differs from the verified reconstruction.');
  const postedWord=requireResult(r[4]),sellWord=requireResult(r[5]),buyWord=requireResult(r[6]),metadata=requireResult(r[7]),lot=uintAt(metadata,7);
  if(lot===0n||Number(uintAt(metadata,1))!==market.decimals)throw Error('Token metadata is unsupported.');
  return {market:market.symbol,decimals:market.decimals,token:market.address,block:n,hash:block.hash,timestamp:parseInt(block.timestamp,16),endpoint,postedWord,postedAge:Math.max(0,parseInt(block.timestamp,16)-Number(BigInt(postedWord)&0xffffffffn)),lotRaw:lot.toString(),inventoryLimitRaw:(lot*uintAt(metadata,8)).toString(),divisor:uintAt(metadata,3)>=3n&&uintAt(metadata,3)<=5n&&uintAt(metadata,4)===0n?2:1,sellSlot,buySlot,sellWord,buyWord,sellStats:decodeStats(sellWord),buyStats:decodeStats(buyWord),engineHash,helperHash};
}
async function snapshotFor(s:Scenario,market:Market):Promise<Snapshot>{
  const key=s.market+':'+(s.block??'latest');if(s.block&&snapshots.has(key))return snapshots.get(key)!;
  const promise=(async()=>{let failure='';for(const p of PROVIDERS){try{return await capture(p,market,s.block);}catch(e){failure=(e as Error).message;}}throw Error('Snapshot unavailable. '+failure);})();
  if(s.block){if(snapshots.size>=12)snapshots.delete(snapshots.keys().next().value!);snapshots.set(key,promise);}
  try{const snapshot=await promise;if(snapshots.size>=12)snapshots.delete(snapshots.keys().next().value!);snapshots.set(s.market+':'+snapshot.block,Promise.resolve(snapshot));return snapshot;}catch(e){snapshots.delete(key);throw e;}
}
export async function simulate(s:Scenario):Promise<Simulation>{
  const market=validateScenario(s),snapshot=await snapshotFor(s,market),requests=s.sizes.flatMap(size=>[simulationCall(snapshot,s,size,false),simulationCall(snapshot,s,size,true)]);
  const rows:SimulationRow[]=[];
  for(let start=0;start<requests.length;start+=8){const r=await batch(snapshot.endpoint,requests.slice(start,start+8));for(let i=0;i<r.length;i++){
    const size=s.sizes[Math.floor((start+i)/2)],buy=(start+i)%2===1;
    try{rows.push(decodeSimulation(requireResult(r[i]),size,market.decimals,buy));}catch(e){rows.push({size,amountRaw:parseUnits(size,market.decimals).toString(),buy,quoteRaw:'0',quoteId:'0',status:'rpc-error',reason:(e as Error).message,gasUsed:0,warmCodeSize:0,fees:{stale:0,callerAndPool:0,volume:0}});}
  }}
  if(rows.every(r=>r.status==='rpc-error'))throw Error('RPC simulation unavailable: '+rows[0].reason);
  const end=await batch(snapshot.endpoint,[{method:'eth_getBlockByNumber',params:['0x'+snapshot.block.toString(16),false]}]);
  if(requireResult(end[0])?.hash!==snapshot.hash){snapshots.delete(s.market+':'+snapshot.block);throw Error('Base reorganized during simulation. Capture a new snapshot.');}
  return {snapshot,scenario:s,rows,effectiveAge:s.age??snapshot.postedAge,createdAt:Date.now(),scope:'Independent quote plus engine update checks using original deployed engine bytecode. Synthetic caller class and optional state overrides. Token transfers, approvals, wrapper checks, future state and multi-fill sequences are not simulated.',probeSourceSha256:probe.sourceSha256};
}
export function defaultScenario(market:string):Scenario{const m=MARKETS.find(m=>m.symbol===market)||MARKETS[0];return {market:m.symbol,callerClass:0,sizes:[...m.sizes],age:null,flow:null,warmRoute:false,gas:30000000,executor:DEFAULT_EXECUTOR};}
