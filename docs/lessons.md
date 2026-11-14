# Lessons from the Wintermute reconstruction

1. **A decompiler is a hypothesis generator.** Control-flow warnings and plausible
   pseudocode need cross-checks against opcodes and execution. Pool variants that
   look similar can differ in token index types, return handling and ETH wrapping.
2. **Compiler pipeline parity comes first.** Compiling extracted Yul separately
   produced differences that were misleading when compared with Solidity viaIR.
   The successful candidate used the normal stock Solidity pipeline.
3. **Source order can affect optimizer output.** Moving two Balancer getter
   definitions after `unkillContract` was decisive in the final layout. Preserve
   successful ordering and record experiments rather than applying broad rewrites.
4. **Selectors do not uniquely identify names.** Seventeen functions needed
   synthetic `recovered_...` names chosen for selector compatibility. The original
   names remain unknown. Their checked hashes and provenance are published.
5. **Constructor execution beats guessing immutable offsets.** Running the
   original and candidate initcode with the recovered six arguments resolves
   immutable addresses and the delay. Both original deployment and candidate are
   checked against runtime evidence without compiler-output substitutions.
6. **Preserve observed quirks.** Ignored token return values and ignored direct-tip
   call failures are part of the deployed behavior. Strengthening those checks
   would create a different contract, even if the change looks desirable.
7. **Finite tests should distinguish competing interpretations.** Mock pool output
   and token balance deliberately differ, exposing whether a path transfers the
   returned amount or the whole balance. Tests also cover permission failures,
   deadline equality, malformed data, approval cleanup and all trade entry points.
8. **Execution mechanics have a narrower scope than strategy.** Calldata and
   transfers reveal execution constraints and payments. They do not by themselves
   reveal CEX fills, realized profits, private submission or the fair-value model.

The case is a successful example, not a guarantee that every contract can be
reconstructed into a verification-compatible source. Assembly-heavy code,
unknown toolchains, missing initcode and state-dependent construction can require
different techniques or limit the attainable result.
