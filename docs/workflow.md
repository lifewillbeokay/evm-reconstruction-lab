# Reconstruction workflow

## 1. Collect before interpreting

Record chain ID, contract address, block number/hash, runtime hash and deployment
transaction. Pin a finalized block when possible. Inspect proxies before
attributing implementation behavior to a proxy shell. Save raw evidence and
keep it distinct from reconstructed source.

`evm-lab collect` uses a read-only RPC endpoint supplied through an environment
variable. It captures runtime and direct-creation input when a matching
deployment transaction is supplied. Factory deployments require creation traces;
their top-level transaction input is not the child contract's initcode.

Check explorer and Sourcify source availability and compiler metadata references
before investing in decompilation. A published metadata/source bundle can make
reconstruction unnecessary. This check is currently manual.

## 2. Recover a structural map

Inspect selectors, revert strings, external-call targets, immutable addresses,
storage slots and dispatch branches. Use [EVMole](https://github.com/cdump/evmole)
for richer interface/storage inference and
[Heimdall](https://github.com/Jon-Becker/heimdall-rs) or
[Panoramix](https://github.com/palkeo/panoramix) for independent decompiler views.
Follow each project's installation and licensing instructions. The lab's linear
disassembler is a primitive, not a replacement for control-flow analysis.

Track how each claim was obtained. A selector-database hit is a candidate;
validate it against calldata layout and actual execution. Unknown names may
remain unknown even when the function's behavior is clear.

## 3. Reconstruct small, testable pieces

Start with constructor configuration, access controls, external calls and
observable effects. Reuse a known dependency only after checking the code
pattern and version. Add semantic fixtures that distinguish plausible meanings:
for example, pool-returned output versus sweeping the executor's full balance.

Keep the source-order and compiler pipeline stable while changing one variable.
Build through stock solc Standard JSON. Preserve remappings, source paths,
optimizer details, EVM target and `viaIR` settings. Cache artifacts by input hash.
The compile script records this hash and compiler warnings alongside its output.

## 4. Validate at the appropriate depth

For an execution report, tested semantics and correctly decoded transactions
may be sufficient. For verification, continue to creation/runtime comparison.
Execute constructors to resolve immutable values; do not substitute bytes and
then describe the patched output as a compiler match.

Add unauthorized, inactive, expired, malformed-return and external-revert cases.
Make clear whether tests use synthetic mocks, forked historical state, or both.
Matching executable bytes provide strong evidence about the reconstructed code,
but do not reveal original names, comments or off-chain trading decisions.

## 5. Publish evidence with the result

Package literal Standard JSON input, constructor arguments, source/dependency
files, selector provenance, compiler details, test scripts and comparison output.
Use [match definitions](match-levels.md) consistently. If submitting to an
explorer, save its actual response and URL; keep local results separate.

Explorer submission is manual in v0.1.0. The repository generates usable inputs
and reproduces evidence but does not accept terms, submit contracts or broadcast
transactions automatically.
