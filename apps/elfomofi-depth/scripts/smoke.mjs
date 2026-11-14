// Explicit live QA, never part of offline unit tests. Read-only public calls.
const origin=process.argv[2]||'http://127.0.0.1:5173';
const reports=[];
const word=n=>BigInt(n).toString(16).padStart(64,'0');
for(const market of ['WETH','cbBTC','AAPLc']){
  const r=await fetch(origin+'/api/book?market='+market);const snapshot=await r.json();
  if(!r.ok)throw new Error(JSON.stringify(snapshot));
  const input=snapshot.sells.find(q=>q.status==='ok')||snapshot.sells[0];
  const index=snapshot.sells.indexOf(input),output=snapshot.buys[index];
  const quote='0x833589fcd6edb6e08f4c7c32d4f71b54bda02913';
  const requests=[false,true].map((buy,i)=>({jsonrpc:'2.0',id:i+1,method:'eth_call',params:[{
    to:'0xffffffbb2d432b8acb4c57d556c0c721a431d038',from:snapshot.sender,gas:'0x1c9c380',gasPrice:'0x1',
    data:'0x'+(buy?'6486c4ac':'561fa97d')+[buy?quote:snapshot.token,buy?snapshot.token:quote,input.amountRaw,snapshot.executor,snapshot.partner].map(word).join(''),
  },'0x'+snapshot.blockNumber.toString(16)]}));
  const replies=await fetch('https://mainnet.base.org',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(requests)}).then(r=>r.json());
  for(const [i,q] of [input,output].entries()){
    const reply=replies.find(r=>r.id===i+1);if(reply.error)throw new Error(JSON.stringify(reply.error));
    const raw=BigInt(reply.result.slice(0,66)).toString();if(raw!==q.quoteRaw)throw new Error(`Independent RPC mismatch for ${market} ${i}`);
  }
  reports.push({market,block:snapshot.blockNumber,engine:snapshot.engine,bidIntervals:snapshot.quotedBid.length,askIntervals:snapshot.quotedAsk.length,independentRpcMatches:2});
}
console.log(JSON.stringify(reports,null,2));
