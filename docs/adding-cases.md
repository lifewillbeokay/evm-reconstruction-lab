# Adding a reconstruction case

Create `cases/<descriptive-name>/` containing:

- `case.json`: chain/address, deployer, constructor context, compiler and file paths.
- `chain-runtime.hex`: observed deployed bytes.
- `chain-creation-input.hex`: actual initcode followed by constructor arguments.
- `constructor-arguments.hex`: the ABI-encoded argument suffix (empty is valid).
- `standard-input.json`: literal sources and exact compiler settings.
- Source/dependency files matching the JSON contents, with licenses preserved.
- `selector-map.json`: every external function signature, selector and provenance.
- `differential.py`: a script accepting `--candidate` and `--output`.
- `README.md`: evidence URLs, findings, attribution and limitations.
- `evidence/`: source receipts and raw or decoded transaction evidence.

Use the first case's `case.json` as a concrete example. `contract` is a
`source/path.sol:ContractName` identifier. `compiler` contains the complete
release plus commit. `evm_fork` controls the local VM (`paris`, `shanghai`, or
`cancun`) and is distinct from the compiler's `evmVersion` setting. Do not assume
that deployed bytecode metadata always ends the initcode; the generic comparator
only separates a recognized terminal CBOR suffix.

Record the original runtime hash and collection block where available. The first
case preserves an explorer snapshot without a single runtime collection block;
that missing provenance is documented rather than invented. New RPC collections
should include the block number and hash.

For a factory deployment, obtain the creation trace. If construction reads
external contracts or depends on historical state, supply a custom harness;
the default zero-value, empty-state constructor runner will not reproduce it.

The selector map currently uses the original case's schema: `selector`,
`signature`, `description`, `mined_name`, `trade_entrypoint`, and
`signature_hash_verified`. `mined_name: false` means no synthetic collision was
used, not that the original name was independently proven.

Add specific expected outcomes to differential tests. Describe watched state
and untested contexts. If external behavior is mocked, avoid presenting that as
a real pool replay or profitability measurement.

Run the case, then write and verify its manifest:

```sh
uv run python scripts/reproduce.py <descriptive-name>
uv run python scripts/evidence.py cases/<descriptive-name> --write
uv run python scripts/evidence.py cases/<descriptive-name>
```

Add a CI reproduction step for the new case and its compiler installation.
Publishing a candidate is not an assertion that it is the original source or
that the deployed contract is safe to operate.

## Behavioral and modular cases

An informative case need not reach executable-bytecode equivalence. Mark it
explicitly as a behavioral reconstruction in `case.json`, and distinguish the
reconstructed component from dependencies executed as captured original bytes.
The [ElfomoFi case](../cases/elfomofi-pricing/README.md) uses a dedicated
`scripts/reproduce-elfomofi.py` runner because its state witness and engine
experiments do not fit the first case's exact-match runner.

Unknown signatures may be null in the selector map when accompanied by the raw
selector, decoded argument types and behavioral provenance. Do not mine a name
merely to satisfy the original case's schema.

Preserve the authentic unmodified replay separately from synthetic state
overrides. Record complete scenario inputs, all reached code/storage needed for
offline reproduction, and explicit limitations of incomplete state coverage.
See [stateful engine analysis](stateful-engine-analysis.md).
