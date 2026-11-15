import {PROXY,SWAP,ENGINE,DEFAULT_EXECUTOR,IMPLEMENTATION_SLOT,MARKETS,word,decodeBook,decodePairs,addressAt,quoteCall,quoteResult,marginalLevels,samplingSizes,uintAt,parseUnits} from './elfomo.ts';
import type {Book,Market,Level} from './elfomo.ts';

export type Reply={id:number;result?:any;error?:{code?:number;message?:string}};
export type Request={method:string;params:unknown[]};
export const PROVIDERS=['https://base-rpc.publicnode.com','https://base.drpc.org','https://public.1rpc.io/base','https://mainnet.base.org'];
const cache=new Map<string,{at:number;promise:Promise<Book>}>();
export async function batch(endpoint:string,requests:Request[]):Promise<Reply[]> {
  const response=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(requests.map((r,i)=>({jsonrpc:'2.0',id:i+1,...r}))),signal:AbortSignal.timeout(10000)});
  if(!response.ok)throw new Error(`RPC returned HTTP ${response.status}.`);
  const raw=await response.json() as Reply[];
  if(!Array.isArray(raw))throw new Error('RPC batch unavailable.');
  const byId=new Map(raw.map(r=>[r.id,r]));
  return requests.map((_,i)=>byId.get(i+1)||{id:i+1,error:{message:'Missing RPC response'}});
}
export function requireResult(r:Reply){if(r.error||r.result===undefined)throw new Error(r.error?.message||'Missing RPC response');return r.result;}
function call(data:string,block:string):Request {return {method:'eth_call',params:[{to:PROXY,from:SWAP,data,gas:'0x1c9c380',gasPrice:'0x1'},block]};}
async function collect(endpoint:string,market:Market,executor:string,partner:string,custom?:string):Promise<Book> {
  const first=await batch(endpoint,[{method:'eth_chainId',params:[]},{method:'eth_getBlockByNumber',params:['latest',false]}]);
  if(requireResult(first[0])!=='0x2105')throw new Error('RPC is not Base mainnet.');
  const block=requireResult(first[1]);if(!block?.hash||!block.number)throw new Error('Block unavailable.');
  const tag=block.number;
  const second=await batch(endpoint,[
    call('0xd527c998',tag),call('0x0a6e04cb'+word(market.address)+word('0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'),tag),
    {method:'eth_getStorageAt',params:[PROXY,market.slot,tag]},
    {method:'eth_getStorageAt',params:[PROXY,IMPLEMENTATION_SLOT,tag]},
  ]);
  const pairs=decodePairs(requireResult(second[0]));
  const activePair=pairs.some(([a,b])=>a===market.address&&b==='0x833589fcd6edb6e08f4c7c32d4f71b54bda02913');
  const engine=addressAt(requireResult(second[2])),implementation=addressAt(requireResult(second[3]));
  let book:[Level[],Level[]]=[[],[]],bookError:string|null=null;
  try{book=decodeBook(requireResult(second[1]),market.decimals);}catch(e){bookError=(e as Error).message;}
  const warnings:string[]=[];
  if(![ENGINE,'0x84cb1a96e57e9b88cf75035384c06dc3769654ae'].includes(engine)){
    book=[[],[]];bookError='The current engine ladder format has not been reviewed. Quote-derived depth remains available.';
    warnings.push(bookError);
  }
  if(!activePair)warnings.push('This pair is no longer listed by the pricing dispatcher.');
  // Storage route and price scales were recovered for this implementation.
  if(implementation!=='0x555a998a43a63d67abfb186b375d8aa56c66790b')throw new Error('The pricing implementation changed. The adapter needs review before publishing depth.');
  if(engine==='0x'+'0'.repeat(40))throw new Error('This pair has no registered pricing engine.');
  const sizes=samplingSizes(market,book,custom);
  const requests:Request[]=sizes.flatMap(n=>[call(quoteCall(market,n,false,executor,partner),tag),call(quoteCall(market,n,true,executor,partner),tag)]);
  if([ENGINE,'0x84cb1a96e57e9b88cf75035384c06dc3769654ae'].includes(engine))requests.push({method:'eth_getStorageAt',params:[engine,'0x2',tag]});
  const replies:Reply[]=[];
  // Bounded batches fit the public RPC services' request limits.
  for(let i=0;i<requests.length;i+=18)replies.push(...await batch(endpoint,requests.slice(i,i+18)));
  const sells=sizes.map((n,i)=>quoteResult(n,market.decimals,replies[2*i]));
  const buys=sizes.map((n,i)=>quoteResult(n,market.decimals,replies[2*i+1]));
  if([...sells,...buys].every(q=>q.status==='error'))throw new Error('All quote calls failed at this RPC provider.');
  const priceWord=replies.at(-1)!;
  const postedTimestamp=![ENGINE,'0x84cb1a96e57e9b88cf75035384c06dc3769654ae'].includes(engine)||priceWord.error?null:Number(uintAt(requireResult(priceWord),0)&0xffffffffn);
  // Confirm no canonical-block replacement occurred while the sweep was running.
  const end=await batch(endpoint,[{method:'eth_getBlockByNumber',params:[tag,false]}]);
  if(requireResult(end[0])?.hash!==block.hash)throw new Error('Base reorganized during the sweep. Refresh to collect a consistent block.');
  if(sells.some(q=>q.status==='error')||buys.some(q=>q.status==='error'))warnings.push('Some quote calls failed. Failed intervals are excluded from depth.');
  return {market:market.symbol,token:market.address,decimals:market.decimals,blockNumber:parseInt(tag,16),blockHash:block.hash,blockTimestamp:parseInt(block.timestamp,16),fetchedAt:Date.now(),rpc:new URL(endpoint).hostname,engine,implementation,executor,partner,sender:SWAP,gas:30000000,gasPrice:'1',postedTimestamp,postedAge:postedTimestamp===null?null:parseInt(block.timestamp,16)-postedTimestamp,bid:book[0],ask:book[1],sells,buys,quotedBid:marginalLevels(sells,market.decimals),quotedAsk:marginalLevels(buys,market.decimals),warnings,bookError,activePair,customSize:custom||null};
}
export async function getBook(params:URLSearchParams):Promise<Book> {
  const symbol=params.get('market')||'WETH',market=MARKETS.find(m=>m.symbol===symbol);
  if(!market)throw new RangeError('Choose WETH, cbBTC, or AAPLc.');
  const executor=(params.get('executor')||DEFAULT_EXECUTOR).toLowerCase(),partner=params.get('partner')||'0',custom=params.get('size')||undefined;
  if(!/^0x[0-9a-f]{40}$/.test(executor))throw new RangeError('Executor must be a 20-byte address.');
  if(!/^\d{1,78}$/.test(partner)||BigInt(partner)>=2n**256n)throw new RangeError('Partner ID must be a uint256.');
  if(custom){try{parseUnits(custom,market.decimals);}catch(e){throw new RangeError((e as Error).message);}}
  const key=[symbol,executor,BigInt(partner).toString(),custom||''].join(':');
  const old=cache.get(key);if(old&&Date.now()-old.at<12000)return old.promise;
  if(cache.size>=32)cache.delete(cache.keys().next().value!);
  const promise=(async()=>{const failures:string[]=[];for(const endpoint of PROVIDERS){try{return await collect(endpoint,market,executor,partner,custom);}catch(e){failures.push(`${new URL(endpoint).hostname}: ${(e as Error).message}`);}}throw new Error('Base data unavailable. '+failures.join(' · '));})();
  cache.set(key,{at:Date.now(),promise});
  try{return await promise;}catch(e){cache.delete(key);throw e;}
}
