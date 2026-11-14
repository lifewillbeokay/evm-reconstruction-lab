export const PROXY = '0xffffffbb2d432b8acb4c57d556c0c721a431d038';
export const SWAP = '0xf0f0f0f0fb0d738452efd03a28e8be14c76d5f73';
export const USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913';
export const ENGINE = '0xd6ac027dbcbf19489e8ecd4d719aa83396eca3ee';
export const DEFAULT_EXECUTOR = '0x1111111111111111111111111111111111111111';
export const IMPLEMENTATION_SLOT = '0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc';
export const MARKETS = [
  {symbol:'WETH',name:'Wrapped Ether',address:'0x4200000000000000000000000000000000000006',decimals:18,slot:'0x8dd3416d6a29f316c400d30cc7a4c4b85a1e84f155430cb54f452b437e5ea11f',sizes:['0.01','0.1','0.5','1','2','5','10','25','50','100']},
  {symbol:'cbBTC',name:'Coinbase Bitcoin',address:'0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf',decimals:8,slot:'0xf8b93bb4caee16b582679e42eb646155e84f0879563b227942d8f3d4f5a4dc29',sizes:['0.001','0.005','0.01','0.02','0.05','0.1','0.25','0.5','1','2']},
  {symbol:'AAPLc',name:'Apple · tokenized equity',address:'0xb200000000000000000000c2e324d24d7eecd1fb',decimals:8,slot:'0x3f43c04475a68b36669a12e99486672f61a4b588e6a4bed986474504a63b427b',sizes:['0.1','1','2','5','10','25','50','100','200','500']},
] as const;
export type Market = (typeof MARKETS)[number];
export type Level = {amountRaw:string;priceRaw:string;quantity:number;price:number;notional:number;cumulativeQuantity:number;cumulativeNotional:number;source:'ladder'|'sample'};
export type Quote = {amountRaw:string;quantity:number;quoteRaw:string|null;quote:number|null;average:number|null;quoteId:string|null;status:'ok'|'unavailable'|'error';error?:string};
export type Book = {
  market:string;token:string;decimals:number;blockNumber:number;blockHash:string;blockTimestamp:number;fetchedAt:number;rpc:string;
  engine:string;implementation:string;executor:string;partner:string;sender:string;gas:number;gasPrice:string;
  postedTimestamp:number|null;postedAge:number|null;bid:Level[];ask:Level[];sells:Quote[];buys:Quote[];
  quotedBid:Level[];quotedAsk:Level[];warnings:string[];bookError:string|null;activePair:boolean;customSize:string|null;
};
export function word(value: string|bigint|number) {return BigInt(value).toString(16).padStart(64,'0');}
export function parseUnits(value:string,decimals:number):bigint {
  if(!/^\d+(\.\d+)?$/.test(value)||value.length>90) throw new Error('Enter a positive decimal amount.');
  const [whole,fraction='']=value.split('.');
  if(fraction.length>decimals) throw new Error(`Use at most ${decimals} decimal places.`);
  const n=BigInt(whole)*10n**BigInt(decimals)+BigInt(fraction.padEnd(decimals,'0')||'0');
  if(n<=0n||n>=2n**256n) throw new Error('Amount is outside the supported range.');
  return n;
}
export function uintAt(hex:string,index:number):bigint {
  if(!/^0x(?:[0-9a-f]{2})*$/i.test(hex)||index<0||!Number.isInteger(index)||2+(index+1)*64>hex.length) throw new Error('Truncated or invalid contract response.');
  return BigInt('0x'+hex.slice(2+index*64,2+(index+1)*64));
}
export function addressAt(hex:string,index=0) {return '0x'+word(uintAt(hex,index)).slice(-40);}
function offsetWords(hex:string,index:number) {
  const bytes=uintAt(hex,index);
  if(bytes%32n!==0n||bytes>BigInt((hex.length-2)/2))throw new Error('Invalid ABI offset.');
  return Number(bytes/32n);
}
export function decodeBook(hex:string,decimals:number):[Level[],Level[]] {
  return [0,1].map(side=>{
    const start=offsetWords(hex,side);const count=Number(uintAt(hex,start));
    if(count>64)throw new Error('Unexpected number of depth levels.');
    let quantity=0,notional=0;
    return Array.from({length:count},(_,i)=>{
      const a=uintAt(hex,start+1+2*i),p=uintAt(hex,start+2+2*i);
      const q=Number(a)/10**decimals,price=Number(p)/1e12,n=q*price;
      quantity+=q;notional+=n;
      return {amountRaw:a.toString(),priceRaw:p.toString(),quantity:q,price,notional:n,cumulativeQuantity:quantity,cumulativeNotional:notional,source:'ladder' as const};
    }).filter(x=>x.quantity>0&&x.price>0);
  }) as [Level[],Level[]];
}
export function decodePairs(hex:string):[string,string][] {
  const start=offsetWords(hex,0),count=Number(uintAt(hex,start));
  if(count>256)throw new Error('Unexpected pair count.');
  return Array.from({length:count},(_,i)=>[addressAt(hex,start+1+2*i),addressAt(hex,start+2+2*i)]);
}
export function quoteCall(market:Market,amount:bigint,buy:boolean,executor:string,partner:string) {
  const a=buy?USDC:market.address,b=buy?market.address:USDC;
  return '0x'+(buy?'6486c4ac':'561fa97d')+[a,b,amount,executor,partner].map(word).join('');
}
export function quoteResult(amount:bigint,decimals:number,result:{result?:string;error?:{message?:string}}):Quote {
  const base={amountRaw:amount.toString(),quantity:Number(amount)/10**decimals};
  if(result.error||!result.result)return {...base,quoteRaw:null,quote:null,average:null,quoteId:null,status:'error',error:result.error?.message?.slice(0,160)||'Missing RPC result'};
  try {
    const q=uintAt(result.result,0),id=uintAt(result.result,1);const quote=Number(q)/1e6;
    return {...base,quoteRaw:q.toString(),quote,average:q>0n?quote/base.quantity:null,quoteId:id.toString(),status:q>0n?'ok':'unavailable'};
  }catch(e){return {...base,quoteRaw:null,quote:null,average:null,quoteId:null,status:'error',error:(e as Error).message};}
}
// An interval is the difference between independent cumulative quotes. Never
// bridge a failed/zero quote, and never invent liquidity beyond the last sample.
export function marginalLevels(quotes:Quote[],decimals:number):Level[] {
  let previousAmount=0n,previousQuote=0n;const levels:Level[]=[];
  for(const q of quotes) {
    if(q.status!=='ok'||q.quoteRaw===null)break;
    const amount=BigInt(q.amountRaw),quote=BigInt(q.quoteRaw);
    if(amount<=previousAmount||quote<=previousQuote)break;
    const deltaAmount=amount-previousAmount,deltaQuote=quote-previousQuote;
    const quantity=Number(deltaAmount)/10**decimals,notional=Number(deltaQuote)/1e6;
    levels.push({amountRaw:deltaAmount.toString(),priceRaw:'',quantity,price:notional/quantity,notional,cumulativeQuantity:q.quantity,cumulativeNotional:Number(quote)/1e6,source:'sample'});
    previousAmount=amount;previousQuote=quote;
  }
  return levels;
}
export function samplingSizes(market:Market,book:[Level[],Level[]],custom?:string):bigint[] {
  const amounts=new Set(market.sizes.map(x=>parseUnits(x,market.decimals).toString()));
  const max=BigInt([...amounts].at(-1)!);
  // Include ladder boundaries to resolve price cliffs without interpolating.
  for(const side of book){let total=0n;for(const l of side){total+=BigInt(l.amountRaw);if(total>0n&&total<=max)amounts.add(total.toString());}}
  if(custom)amounts.add(parseUnits(custom,market.decimals).toString());
  return [...amounts].map(BigInt).sort((a,b)=>a<b?-1:a>b?1:0);
}
// Preserve fill order, using the worst price encountered so far for depth at a
// price threshold. Sorting intervals alone could imply unreachable cheap depth.
export function depthAt(levels:Level[],side:'bid'|'ask',mid:number,bps:number,unit:'quote'|'base'='quote') {
  let total=0;
  for(const l of levels){const deviation=(l.price/mid-1)*10000;if(side==='bid'?deviation < -bps:deviation > bps)break;total+=unit==='quote'?l.notional:l.quantity;}
  return total;
}
