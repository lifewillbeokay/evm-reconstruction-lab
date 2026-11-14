import test from 'node:test';
import assert from 'node:assert/strict';
import {getBook} from '../lib/rpc.ts';
import {word,MARKETS,USDC,IMPLEMENTATION_SLOT,ENGINE} from '../lib/elfomo.ts';
const originalFetch=globalThis.fetch;
const hash='0x'+'ab'.repeat(32);
const otherEngine='0x84cb1a96e57e9b88cf75035384c06dc3769654ae';
test('single-block reads, route changes, quote batch errors and input validation',async()=>{
  const seen:any[]=[];
  globalThis.fetch=async (_url:any,init:any)=>{
    const requests=JSON.parse(init.body);seen.push(...requests);
    const answers=requests.map((r:any)=>{
      let result:any;
      if(r.method==='eth_chainId')result='0x2105';
      else if(r.method==='eth_getBlockByNumber')result={number:'0x100',hash,timestamp:'0x1000'};
      else if(r.method==='eth_getStorageAt')result='0x'+word(r.params[1]===IMPLEMENTATION_SLOT?'0x555a998a43a63d67abfb186b375d8aa56c66790b':otherEngine);
      else if(r.method==='eth_call'){
        const data=r.params[0].data;
        if(data.startsWith('0xd527c998'))result='0x'+[32,1,MARKETS[0].address,USDC].map(word).join('');
        else if(data.startsWith('0x0a6e04cb'))result='0x'+[64,96,0,0].map(word).join('');
        else if(data.startsWith('0x561fa97d'))return {jsonrpc:'2.0',id:r.id,error:{code:-32000,message:'fixture quote unavailable'}};
        else result='0x'+[10000000,42,96,0].map(word).join('');
      }return {jsonrpc:'2.0',id:r.id,result};
    });
    return Response.json(answers.reverse()); // replies may arrive out of order
  };
  try{
    const params=new URLSearchParams({market:'WETH',partner:'791'});
    const data=await getBook(params);
    assert.equal(data.engine,otherEngine);assert.equal(data.blockHash,hash);assert.equal(data.postedAge,null);
    assert.equal(data.sells[0].status,'error');assert.equal(data.buys[0].status,'ok');assert.equal(data.quotedBid.length,0);
    assert(seen.filter(x=>['eth_call','eth_getStorageAt'].includes(x.method)).every(x=>x.params.at(-1)==='0x100'));
    assert(!seen.some(x=>x.method==='eth_getStorageAt'&&x.params[0]===otherEngine)); // no old storage layout assumptions
    assert(seen.filter(x=>x.method==='eth_getBlockByNumber').length===2);
    const count=seen.length;await getBook(params);assert.equal(seen.length,count); // request coalescing/cache
    await assert.rejects(getBook(new URLSearchParams({executor:'bad'})),RangeError);
    await assert.rejects(getBook(new URLSearchParams({size:'0'})),RangeError);
  }finally{globalThis.fetch=originalFetch;}
});
test('a changed canonical block is rejected, not presented as coherent depth',async()=>{
  globalThis.fetch=async (_url:any,init:any)=>Response.json(JSON.parse(init.body).map((r:any)=>{
    let result:any;
    if(r.method==='eth_chainId')result='0x2105';
    else if(r.method==='eth_getBlockByNumber')result={number:'0x100',hash:r.params[0]==='latest'?hash:'0x'+'cd'.repeat(32),timestamp:'0x1000'};
    else if(r.method==='eth_getStorageAt')result='0x'+word(r.params[1]===IMPLEMENTATION_SLOT?'0x555a998a43a63d67abfb186b375d8aa56c66790b':otherEngine);
    else if(r.params[0].data.startsWith('0xd527c998'))result='0x'+[32,1,MARKETS[0].address,USDC].map(word).join('');
    else if(r.params[0].data.startsWith('0x0a6e04cb'))result='0x'+[64,96,0,0].map(word).join('');
    else result='0x'+[10000000,42,96,0].map(word).join('');
    return {id:r.id,result};
  }));
  try{await assert.rejects(getBook(new URLSearchParams({partner:'792'})),/reorganized/);}finally{globalThis.fetch=originalFetch;}
});
