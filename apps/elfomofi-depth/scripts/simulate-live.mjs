// Explicit read-only RPC integration checks. Excluded from offline CI.
// Uses a fixed captured block for repeatable price/guard boundaries, then current routes.
import assert from 'node:assert/strict';
import {simulate,defaultScenario} from '../lib/simulation.ts';
const base={...defaultScenario('WETH'),block:57962726,sizes:['0.01']};
const cases=[
  ['baseline',{},'passes',0],['class2',{callerClass:2},'passes',0],
  ['age7',{age:7},'passes',250],['age11',{age:11},'passes',255],
  ['age11-warm',{age:11,warmRoute:true},'passes',0],['age16',{age:16},'no-quote',0],
  ['count15',{flow:{count:15,large:0,veryLarge:0,volumeLots:'2',oppositeVeryLarge:0}},'passes',0],
  ['count16',{flow:{count:16,large:0,veryLarge:0,volumeLots:'2',oppositeVeryLarge:0}},'guard-reverted',0],
  ['large11',{flow:{count:11,large:11,veryLarge:0,volumeLots:'22',oppositeVeryLarge:0}},'guard-reverted',0],
  ['large-both6',{flow:{count:6,large:6,veryLarge:6,volumeLots:'48',oppositeVeryLarge:6}},'guard-reverted',0],
  ['large-one-side6',{flow:{count:6,large:6,veryLarge:6,volumeLots:'48',oppositeVeryLarge:5}},'passes',0],
];
const report=[];
for(const [name,overrides,status,stale] of cases){const r=await simulate({...base,...overrides});for(const row of r.rows){assert.equal(row.status,status,name);assert.equal(row.fees.stale,stale,name);if(name==='class2')assert.equal(row.fees.callerAndPool,170);if(name==='count16')assert.equal(row.reason,'blk');}if(name==='baseline'){assert.equal(r.rows[0].quoteRaw,'18276634');assert.equal(r.rows[1].quoteRaw,'18277366');}report.push({name,block:r.snapshot.block,status,rows:r.rows.length});}
for(const market of ['WETH','cbBTC','AAPLc']){const s=defaultScenario(market);s.sizes=s.sizes.slice(0,2);const r=await simulate(s);assert(r.rows.every(x=>x.status!=='rpc-error'));report.push({name:'current-'+market,block:r.snapshot.block,status:r.rows.map(r=>r.status),rows:r.rows.length});}
console.log(JSON.stringify({scope:'Read-only original-engine quote + update checks; no settlement or broadcasts',scenarios:report},null,2));
