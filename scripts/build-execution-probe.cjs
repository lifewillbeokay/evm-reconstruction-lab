// Build the browser's read-only RPC instrumentation with the pinned compiler.
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto');
const solc=require('solc-0.8.34');
const root=path.resolve(__dirname,'..'), app=path.join(root,'apps/elfomofi-depth');
const source=fs.readFileSync(path.join(app,'contracts/ExecutionProbe.sol'),'utf8');
if(!solc.version().startsWith('0.8.34+commit.80d5c536'))throw Error('Unexpected compiler');
const input={language:'Solidity',sources:{'ExecutionProbe.sol':{content:source}},settings:{viaIR:true,evmVersion:'cancun',optimizer:{enabled:true,runs:100},outputSelection:{'*':{'*':['abi','evm.deployedBytecode.object','evm.methodIdentifiers']}}}};
const result=JSON.parse(solc.compile(JSON.stringify(input)));
const errors=(result.errors||[]).filter(x=>x.severity==='error');if(errors.length)throw Error(errors.map(x=>x.formattedMessage).join('\n'));
const c=result.contracts['ExecutionProbe.sol'].ExecutionProbe;
const artifact={compiler:solc.version(),sourceSha256:crypto.createHash('sha256').update(source).digest('hex'),runtime:'0x'+c.evm.deployedBytecode.object,selector:'0x'+c.evm.methodIdentifiers['simulate(address,uint256,bool,uint8,address,bool)'],abi:c.abi};
const file=path.join(app,'lib/execution-probe.json'),text=JSON.stringify(artifact,null,2)+'\n';
if(process.argv.includes('--check')){if(fs.readFileSync(file,'utf8')!==text)throw Error('Execution probe artifact is stale');}
else fs.writeFileSync(file,text);
console.log(JSON.stringify({compiler:artifact.compiler,runtimeBytes:(artifact.runtime.length-2)/2,sourceSha256:artifact.sourceSha256,checked:process.argv.includes('--check')}));
