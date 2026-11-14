# Investigating modular pricing contracts

The [ElfomoFi case](../cases/elfomofi-pricing/README.md) demonstrates a workflow for
contracts whose pricing logic is spread across a proxy, dispatcher, engines and
external state. A short verified proxy or router can conceal a much larger
unverified decision system.

1. Pin a finalized block and its hash before reading code or storage. Resolve
   proxy slots, read the dispatcher table, and capture every reached implementation.
   Record source verification status separately for each address.
2. Use a verified public wrapper's interface to identify known selectors. Keep
   unknown selectors as raw dispatch; a guessed or mined name is not original
   source provenance.
3. Recover storage layouts through opcode use and public getters. Validate the
   bit packing with an independent decoder. Keep unresolved fields unnamed.
4. Build a local EVM harness that loads captured code and storage on demand.
   During evidence collection, fetch missing reads at the pinned block. During
   offline reproduction, fail on missing reads rather than supply zeros.
5. Replay an unmodified RPC call first, including its sender. A zero or reverting
   result is a result; do not silently replace it with a more interesting quote.
6. Explore branches with explicit, minimal overrides. Label synthetic posted
   prices, time shifts, balances and module substitutions as counterfactuals.
   Freeze unrelated state so the comparison has an interpretable cause.
7. For stateful updates, distinguish transaction-local transient storage from
   persistent state. Clear transient storage between transactions. Compare equal
   total volume split into different numbers of updates, and test block-number
   changes independently of timestamp changes.
8. Reconstruct arithmetic separately from the bytecode harness. Exact per-level
   rounding is testable without pretending to recover the full ladder builder.
9. Substitute the candidate component into the original system. Synthetic unit
   fixtures alone can miss ABI, proxy-context or nested-call differences.
10. Publish captured bytes, scenario inputs, expected results, compiler inputs
    and a manifest. Preserve unfavorable results and explicit scope limits.

Interpret results at the tested scope. A classifier stub proves that the engine
responds differently to classes; it does not explain assignment of real traders.
An inventory override can isolate quote sensitivity but is not an executed swap.
A public RPC state witness is not cryptographic proof of the chain state. A
compiler version in metadata does not uniquely determine its optimizer settings.

Useful extensions include additional historical states, full swaps through the
entry wrapper, exact-output paths, other assets and directions, reference modes,
and a complete independent engine implementation. These should expand measured
coverage rather than merely increase the number of nearly identical tests.
