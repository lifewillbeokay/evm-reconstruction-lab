# What a match means

| Result | Evidence | Limits |
|---|---|---|
| Signature-compatible | Keccak(signature) starts with the target selector | Four bytes admit collisions; names and even argument types may be ambiguous |
| Behavior agrees in tests | Identical observed outputs, calls, logs and watched state for specified fixtures | Finite tests are not equivalence proofs; mocks omit real venue behavior |
| Executable bytes match | Byte-for-byte equality after recognized terminal CBOR is separated | Metadata separation is structural; unusual code may read its own metadata |
| Full runtime matches | Every deployed byte matches after constructor execution | Does not establish original source text or constructor behavior |
| Creation bytes match | Initcode comparison with constructor arguments handled separately | Context-dependent constructors need a faithful environment |
| Metadata matches | Recognized terminal metadata bytes match | Inspect source hashes and compiler metadata; labels alone are insufficient |
| Explorer accepts source | Recorded explorer response | Explorer rules can differ; do not infer a badge or full-bytecode match from local tests |

The first case has matching executable creation/runtime bytes, different source
metadata, 62 passing synthetic behavior cases, and an accepted Etherscan
submission. Its original source text has not been recovered.

The metadata parser accepts a complete terminal CBOR map with recognized
compiler/source-hash keys. It uses the final two-byte length, consumes the whole
map, and retains unrecognized suffixes in the executable comparison. It never
blindly removes a fixed number of bytes. See Solidity's
[metadata documentation](https://docs.soliditylang.org/en/latest/metadata.html).

`capture()` compares nested calls (including calls that later revert), return
data, failure status, logs, watched storage slots and watched balances. Gas is
excluded. External account code changes, unwatched storage and every possible
execution context are not compared automatically. Supply relevant watchlists
and add semantic assertions independent of candidate/original equality.

The local VM applies messages with revert rollback and value transfer. It is
not a signed transaction simulator: intrinsic gas, fees, nonces and block
construction are outside its scope. The default constructor runner uses empty
synthetic state and zero value. The first case reproduces the recorded runtime
in that environment; other contracts may require historical state and factory
creation traces.
