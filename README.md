# EVM Reconstruction Lab

[![Validation](https://github.com/lifewillbeokay/evm-reconstruction-lab/actions/workflows/validate.yml/badge.svg)](https://github.com/lifewillbeokay/evm-reconstruction-lab/actions/workflows/validate.yml)

Tools and documented case studies for turning deployed EVM bytecode into
testable, reproducible source reconstructions. Start with captured evidence,
inspect the code, develop a candidate, and measure what actually matches.

The first case is an independently reconstructed Wintermute-associated
[Curve/Balancer executor](cases/wintermute-curve-balancer/README.md), now
[verified on Etherscan](https://etherscan.io/address/0xec6fc9be2d5e505b40a2df8b0622cd25333823db#code).
Stock Solidity produces matching creation and runtime executable bytes;
the original source metadata hash differs. The case covers **42 external
function selectors, 11 trade entry points, and 62 differential test cases**.

The second case studies [ElfomoFi pricing on Base](cases/elfomofi-pricing/README.md):
a 15-selector dispatcher reconstruction, five captured pricing engines, and
65 controlled WETH/USDC experiments. It recovers inventory, age, caller-class
and within-block pricing behavior. The dispatcher passes 84 differential tests
but **does not match deployed bytecode**; the full engine source is not recovered.

A [live ElfomoFi virtual order book](apps/elfomofi-depth/README.md) now samples
current Base quotes at one block, compares them with the engine ladder, and
exports reproducible snapshots. It follows the current routed engine; it does
not assume the historical case-study address is still active.

This is a reconstruction workbench. It does not automatically recover arbitrary
contracts' source or prove behavioral equivalence in every possible state.

## Reproduce the first case

Requirements: Python 3.11+, Node.js 20+, npm, and [uv](https://docs.astral.sh/uv/).
Dependencies are locked in `uv.lock` and `package-lock.json`.

```sh
git clone https://github.com/lifewillbeokay/evm-reconstruction-lab.git
cd evm-reconstruction-lab
uv sync --frozen --extra dev
npm ci --ignore-scripts
uv run --frozen pytest -q
uv run --frozen python scripts/evidence.py cases/wintermute-curve-balancer
uv run --frozen python scripts/reproduce.py
```

Compilation, constructor execution, and behavioral tests use local files after
dependency installation. They require no RPC endpoint, wallet, or API key.
Results are written to `build/wintermute-curve-balancer/`.

To reproduce the ElfomoFi case with the same installed dependencies:

```sh
uv run --frozen python scripts/evidence.py cases/elfomofi-pricing
uv run --frozen python scripts/reproduce-elfomofi.py
```

Its captured state, explicit counterfactual experiments and independent ladder
arithmetic also run offline. Results go to `build/elfomofi-pricing/`.

Expected result:

| Check | Result |
|---|---|
| Original constructor reproduces recorded runtime | Pass |
| Creation executable bytes | Match, 14,230 total creation bytes |
| Deployed executable bytes | Match, 13,759 total runtime bytes |
| Full bytecode including metadata | Different |
| Selector-compatible signatures | 42/42 |
| Synthetic differential cases | 62/62 |
| Explorer submission | Accepted; receipt included |

The byte counts above include metadata. Constructor arguments are another 192
bytes. No compiler output is patched to obtain a match. Constructor execution
resolves immutable values naturally.

## Reusable commands

```sh
# Metadata and PUSH4 constants. These constants are candidates, not an ABI.
uv run evm-lab inspect cases/wintermute-curve-balancer/chain-runtime.hex

# Opcode listing, with byte offsets and truncated PUSH detection.
uv run evm-lab disassemble cases/wintermute-curve-balancer/chain-runtime.hex

# Keccak selector and calldata decoding with an explicit signature.
uv run evm-lab selector 'transfer(address,uint256)'
uv run evm-lab decode 'transfer(address,uint256)' @path/to/calldata.hex

# A nonzero exit code signals a mismatch under the requested criterion.
uv run evm-lab compare original.hex candidate.hex --require executable
uv run evm-lab compare original.hex candidate.hex --require exact

# Read-only collection; provide your endpoint through ETH_RPC_URL.
uv run evm-lab collect 0xec6fc9be2d5e505b40a2df8b0622cd25333823db \
  --block finalized --output build/new-snapshot
```

`collect` pins a mined block, checks for reorganization, and records code hashes.
It recognizes canonical EIP-1167 clones and records EIP-1967 implementation/beacon
slot candidates. Beacon resolution, factory creation traces and historical state
collection remain manual. Endpoint URLs are never written into evidence files.

See [CLI reference](docs/cli.md) for compiler input generation, constructor
verification, bounded selector mining and exit codes. Python libraries live in
[`src/evm_lab`](src/evm_lab).

## Workflow and documentation

- [Reconstruction workflow](docs/workflow.md): evidence, decompilers, compiler matching and validation.
- [Match definitions and limitations](docs/match-levels.md): what each result establishes.
- [Lessons from the first reconstruction](docs/lessons.md): compiler pipeline traps and selector provenance.
- [Adding a case](docs/adding-cases.md): case format and review requirements.
- [Wintermute case study](cases/wintermute-curve-balancer/README.md): verified build and execution findings.
- [ElfomoFi case study](cases/elfomofi-pricing/README.md): dispatcher reconstruction and pricing experiments.
- [Stateful engine analysis](docs/stateful-engine-analysis.md): reproducible proxy, state-witness and counterfactual workflow.
- [Contributing](CONTRIBUTING.md): tests and changes to evidence.

The workflow can use [Heimdall](https://github.com/Jon-Becker/heimdall-rs) for
decompilation and [EVMole](https://github.com/cdump/evmole) for interface/storage
inference. Those optional external tools are not bundled or required by this
release. Candidate source construction and interpretation remain analyst work.

## Repository layout

```text
src/evm_lab/                    Reusable Python libraries and CLI
scripts/compile.cjs             Stock solc Standard JSON runner
scripts/reproduce.py            Compile + validate a case
scripts/reproduce-elfomofi.py    Compile dispatcher + replay engine experiments
tools/                         Optional Apple Metal selector miner
cases/wintermute-curve-balancer/
  src/ and lib/                Submitted Solidity and dependencies
  standard-input.json          Exact self-contained submission input
  case.json                    Deployment and compiler context
  evidence/                    Submission receipt and decoded transactions
  expected/                    Results recorded during reconstruction
  differential.py              Reproducible synthetic EVM tests
cases/elfomofi-pricing/         Dispatcher source, captured state and pricing lab
docs/                          Methodology and operational details
tests/                         Reusable-tool regression tests
```

## Licensing and attribution

Original toolkit code and documentation are MIT licensed. The reconstructed
executor retains its **UNLICENSED** designation and is an independent reconstruction,
not an official Wintermute release. Vendored OpenZeppelin files retain their MIT
license. See [NOTICE](NOTICE) for the explicit scope of these licenses.
The ElfomoFi dispatcher reconstruction is also UNLICENSED; its public pricing
interface retains its MIT identifier. Neither case is an official project release.
