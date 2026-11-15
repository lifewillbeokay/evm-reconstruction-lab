# ElfomoFi current pricing engine: reconstruction in progress

This case preserves the Base engine at
[`0x84cb1a96e57e9b88cf75035384c06dc3769654ae`](https://basescan.org/address/0x84cb1a96e57e9b88cf75035384c06dc3769654ae#code).
It is separate from the earlier dispatcher and `0xd6ac…` engine case.
**The full engine has not yet been reconstructed or verified.** The Solidity
source in this checkpoint reconstructs the smaller fee helper, with differential
validation. Its executable bytecode is not yet identical to the target either.

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

Remaining work includes the full engine source, validation of its reconstructed
constructor, compiler settings and bytecode matching, broader checks, and the Basescan
submission. The compiler version is observed. Candidate optimization settings
are experimental and are not claimed to be the original settings.

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
