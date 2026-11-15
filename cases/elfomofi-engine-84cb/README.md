# ElfomoFi current pricing engine: reconstruction in progress

This case preserves the Base engine at
[`0x84cb1a96e57e9b88cf75035384c06dc3769654ae`](https://basescan.org/address/0x84cb1a96e57e9b88cf75035384c06dc3769654ae#code).
It is separate from the earlier dispatcher and `0xd6ac…` engine case.
**The full engine has not yet been reconstructed or verified.** This checkpoint
reconstructs the constructor, nine of the twelve external selectors, fallback,
reference-price selection, and the public order-book builder. The three missing
selectors are `getAmountIn`, `getAmountOut` and `update`. Neither the partial parent
nor the reconstructed fee helper matches the target executable bytecode yet.

## Evidence and remaining work

The deployment transaction is
[`0xee98…198b5`](https://basescan.org/tx/0xee98e76f2482e9df90f37ad1de66b60810fc523ddb9ee2590805bda1596198b5).
The deployed engine is 24,500 bytes; its CBOR identifies Solidity 0.8.34.
Its constructor creates the 816-byte helper at
[`0x42e8…d8cbc`](https://basescan.org/address/0x42e88fbc20c66bfe4bac17892980b640990d8cbc#code).
The helper's captured runtime equals the runtime embedded in the parent's
creation input.

The checkpoint contains the deployment, finalized block, constructor arguments,
runtime, a strict state witness and three RPC-backed replay fixtures. These
fixtures exercise the WETH book and both quote directions. They establish a
baseline for future reconstructed engine code; replaying original bytecode is
not itself a source reconstruction.

The original creation input reproduces both the entire engine runtime and the
child helper runtime. AAPLc's `decimals()` call is handled by an explicit native
fixture: its recorded code is only `0xef`, because
[B20 executes inside Base's node](https://www.base.org/blog/introducing-base-beryl).
The fixture accepts only the captured static `decimals()` call from the engine
and returns the deployment-block RPC result, eight. It does not model native
gas charges or other B20 methods. Other dependency code/storage comes from the
finalized snapshot, so this is not a complete signed-transaction replay.

Remaining work includes exact quoting, caller classification, trade accounting,
compiler settings and bytecode matching, broader checks, and Basescan submission.
The compiler version is observed. Candidate optimization settings are experimental
and are not claimed to be the original settings.

## Reconstructed parent behavior

[`src/EngineState.sol`](src/EngineState.sol) is a partial candidate, not original
source and not a contract to deploy. Its constructor validates token metadata and
external reference configurations, records the token order, initializes both side
counters to 1,000, and conditionally creates the fee helper. Administrative calls
use the owner or twenty embedded operator addresses. Packed price updates clamp
future timestamps to the current block time; they preserve old timestamps.

Each posted price occupies 28 bits: a 22-bit mantissa and a signed 6-bit adjustment.
The engine scales prices to 12 decimals and interprets the adjustment in units of
1/100,000. The external-reference modes include no reference, two timestamped
oracle formats, a pool's square-root price, a pool-manager square-root price, and
the average of both pool references. The timestamped formats expire at ages of
120 and 45 seconds respectively. Pool references use metadata-controlled ages.

For ordinary origins with reference checking enabled, a missing reference or
excessive posted/reference deviation produces a zero price. Within the allowed
deviation, a newer posted price wins; otherwise bid and ask selection can use the
lower and higher prices respectively, with a tighter rule for some pool modes.
The owner and four transformed-origin matches take a separate selection path.
These are observed branches, not claims about the identities or intentions of
those callers. Reference calls still occur on that special path and can revert.

The captured parameters add 250 spread units after six seconds, 350 after eight,
and 450 after ten. These equal 25, 35 and 45 basis points. The public book becomes
empty on either side when that side's price is zero or the posted age exceeds
15 seconds. The reconstructed quote paths are not yet available for extending
these observations to every execution route.

The book uses configured `(lot count, spread)` levels. The ask side normally
reserves one lot for a final level with 50,000 additional spread units; a flag can
disable that reserve. Near the inventory boundary, selected levels receive an
additional metadata-controlled penalty. The bid side first checks the inventory
target and quote-token balance, and can include a wide-spread tail sized at five
times the configured inventory target. It then trims the ladder to available
quote funds using the recovered rounding rules. These describe the public book;
additional execution constraints remain to be reconstructed.

The current candidate has a 10,725-byte runtime versus the deployed 24,500 bytes.
The size difference is not a measure of completion or behavioral coverage.

## Validation scope

The parent checkpoint passes 2,660 differential scenarios:

| Scope | Scenarios |
| --- | ---: |
| Constructor metadata and validation | 102 |
| Constructor reference-pool modes | 90 |
| Metadata, administration, authorization and fallback | 234 |
| Price decoding, oracle formats, scaling and arithmetic | 409 |
| Price selection, quote-ID packing and special origins | 1,047 |
| Internal book construction and inventory boundaries | 720 |
| Public book, including one captured RPC result | 58 |

Constructor checks compare rejection data, resulting storage and external calls,
excluding the returned child runtime, which is compared separately. State checks
also compare logs. Internal price/book checks seed stack and memory at recovered
entry points in the original runtime and compare them with a test-only Solidity
harness. They are synthetic function experiments, not transaction replays. Public
book checks execute the candidate's actual external entry point and compare full
call trees. No gas-equivalence or exhaustive-state proof is claimed.

`parent-standard-input.json` preserves exact candidate inputs. The Math library
is vendored unchanged from OpenZeppelin Contracts v4.9.6 under its MIT license;
see [`src/vendor/PROVENANCE.md`](src/vendor/PROVENANCE.md). This is a candidate
dependency choice, not proof that the original author imported that version.
Mined selector collisions are explicitly marked and independently hash-checked;
they do not recover original function names.

## New fee helper

The helper exposes selector `0xb88c9148`, consistent with `getFee(address)`.
The name is a matching signature, not proof of the author's original source.
Other source identifiers and comments are analyst labels.

| Token | Reference pool |
| --- | --- |
| WETH | `0x72ab388e2e2f6facef59e3c3fa2c4e29011c2d38` |
| cbBTC | `0xb94b22332abf5f89877a14cc88f2abc48c34b3df` |
| Other tokens | Returns zero |

For a supported token, the helper reads `slot0()` with an 8,000-gas limit. It
checks the tick range, observation cardinality and index, and reads the latest
and previous `observations(uint256)` entries with 6,000 gas per call. Observation
words must contain canonical uint32 timestamps, int56 cumulative ticks and an
initialized flag equal to one. Unused return words are not validated.

The adjustment is nonzero only when the latest observation timestamp equals
`uint32(block.timestamp)` and both observations are valid. Let `dt` be their
uint32-wrapped timestamp difference and `dc` their int56-wrapped cumulative tick
difference. The recovered rule is:

```text
averageTick = truncTowardZero(dc / dt)
adjustment = min((abs(currentTick - averageTick) + 1) * 10, 1000)
```

Zero elapsed time, an out-of-range average tick, invalid pool data or failed
pool calls yield zero. Even an unchanged tick produces 10 units if the other
conditions hold. This is a recent-observation comparison, not a fixed-duration
TWAP query.

The parent calls the helper with 35,000 gas, accepts exactly one returned word
at most 1,000, and otherwise uses zero. Controlled replacements of the helper
show that its value widens both bid and ask prices. Units are 1/100,000, so an
adjustment of 100 adds 10 basis points to each side; 1,000 adds 100 basis points.
The public book and exact quotes both respond to the adjustment. The experiment
also confirms that 1,001 and uint256.max are ignored, rather than clamped.

This mechanism is consistent with protection against reference-pool movement
within the current block while the separately posted ElfomoFi price lags.
That purpose is an inference; the arithmetic and call behavior are observed.
The captured finalized block returned zero for both supported tokens. The
nonzero examples are controlled offline experiments, not historical fee claims.

## Reproduction

```sh
uv run --frozen python scripts/evidence.py cases/elfomofi-engine-84cb
uv run --frozen python scripts/reproduce-elfomofi-engine.py
```

All reproduction runs offline with the stock pinned compiler. Reports separate
executable, metadata, full-bytecode and behavioral results. No transaction is
broadcast, and no explorer verification has been submitted for this checkpoint.
