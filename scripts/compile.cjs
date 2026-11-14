// Compile literal Standard JSON using stock solc. Never patches compiler output.
const fs = require('node:fs');
const path = require('node:path');
const [inputFile, outputFile, identifier, expectedVersion] = process.argv.slice(2);
if (!inputFile || !outputFile || !identifier || !expectedVersion) {
  console.error('Usage: node scripts/compile.cjs INPUT OUTPUT FILE:CONTRACT EXPECTED_VERSION');
  process.exit(2);
}
// An alternate, explicitly installed compiler can be selected without editing this script.
const solc = process.env.SOLC_MODULE ? require(path.resolve(process.env.SOLC_MODULE)) : require('solc');
const actualVersion = solc.version();
if (!(actualVersion === expectedVersion || actualVersion.startsWith(expectedVersion + '.'))) {
  throw new Error(`Compiler mismatch: expected ${expectedVersion}, got ${actualVersion}`);
}
const input = JSON.parse(fs.readFileSync(inputFile, 'utf8'));
for (const [name, value] of Object.entries(input.sources || {})) {
  if (typeof value.content !== 'string') throw new Error(`Source must be literal content: ${name}`);
}
const output = JSON.parse(solc.compile(JSON.stringify(input)));
const errors = (output.errors || []).filter(e => e.severity === 'error');
if (errors.length) throw new Error(errors.map(e => e.formattedMessage).join('\n'));
const colon = identifier.lastIndexOf(':');
const artifact = output.contracts?.[identifier.slice(0, colon)]?.[identifier.slice(colon + 1)];
if (!artifact?.evm?.bytecode || !artifact?.evm?.deployedBytecode || !artifact?.evm?.methodIdentifiers) {
  throw new Error('Contract missing or outputSelection lacks evm.bytecode, evm.deployedBytecode, evm.methodIdentifiers');
}
fs.mkdirSync(path.dirname(outputFile), {recursive: true});
fs.writeFileSync(outputFile, JSON.stringify(artifact, null, 2) + '\n');
fs.writeFileSync(outputFile + '.build.json', JSON.stringify({compiler:actualVersion, contract:identifier,
  warnings:output.errors || [], inputSha256:require('node:crypto').createHash('sha256').update(fs.readFileSync(inputFile)).digest('hex')}, null, 2) + '\n');
console.log(JSON.stringify({compiler:actualVersion, contract:identifier, output:outputFile,
  creationBytes:artifact.evm.bytecode.object.length / 2, runtimeTemplateBytes:artifact.evm.deployedBytecode.object.length / 2}));
