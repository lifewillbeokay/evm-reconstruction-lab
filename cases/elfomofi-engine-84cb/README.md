# ElfomoFi current pricing engine: reconstruction in progress

This case preserves the Base engine at
[`0x84cb1a96e57e9b88cf75035384c06dc3769654ae`](https://basescan.org/address/0x84cb1a96e57e9b88cf75035384c06dc3769654ae#code).
It is separate from the earlier dispatcher and `0xd6ac…` engine case.
**The complete parent runtime executable and its 4,364-byte constructor prefix
now match exactly. Basescan verification remains pending.** The reconstructed
source covers the constructor, all twelve external selectors, fallback, reference
pricing, book construction, exact quotes, and trade updates. The embedded fee
helper still differs at 17 executable byte positions. The two metadata hashes
also differ, so neither complete creation bytecode nor full runtime bytecode is
claimed to match.

## Evidence and remaining work

The deployment transaction is
[`0xee98…198b5`](https://basescan.org/tx/0xee98e76f2482e9df90f37ad1de66b60810fc523ddb9ee2590805bda1596198b5).
The deployed engine is 24,500 bytes; its CBOR identifies Solidity 0.8.34.
Its constructor creates the 816-byte helper at
[`0x42e8…d8cbc`](https://basescan.org/address/0x42e88fbc20c66bfe4bac17892980b640990d8cbc#code).
The helper's captured runtime equals the runtime embedded in the parent's
creation input.

A [publication-time route check](evidence/publication-route-check.json) at finalized
block 57,935,202 still routes WETH, cbBTC and AAPLc to this engine
with the captured runtime hash. This is a dated observation, not a permanent route.

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

The parent compiles with stock Solidity 0.8.34, the default optimizer at 100 runs,
via IR, targeting Cancun. The candidate constructor is actually executed against
the recorded dependencies and constructor arguments; its returned runtime is
compared with the captured deployed runtime, including immutable values. This
reproduces all 24,447 parent executable bytes. The original metadata hash and
source identifiers remain unknown.

[`expected/creation-bytecode-match.json`](expected/creation-bytecode-match.json)
accounts for every byte of the 29,706-byte creation code:

| Region | Bytes | Result |
| --- | ---: | --- |
| Parent constructor prefix | 4,364 | Exact |
| Parent runtime executable, with immutable placeholders | 24,447 | Exact |
| Parent metadata | 53 | Different |
| Embedded helper constructor | 26 | Exact |
| Embedded helper runtime executable | 763 | 17 differing byte positions, starting at offset 738 |
| Embedded helper metadata | 53 | Different |

Only recognized CBOR metadata regions are excluded from executable comparisons.
The remaining helper differences are executable and are not ignored. Reproduction
checks these reports against fresh compiler output; a passing behavioral suite
cannot replace a bytecode match. Remaining work is the helper's exact executable
match, complete creation matching excluding metadata, and Basescan submission.
The successful settings reproduce this candidate; they are not proof of the
original build configuration. See [source fidelity notes](../../docs/bytecode-fidelity.md)
for the reusable lessons from reaching this match.

## Reconstructed parent behavior

[`src/EngineState.sol`](src/EngineState.sol) is an independent candidate, not original
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

Inverting a pool reference divides `10 ** (baseDecimals + quoteDecimals)` by the
decoded ratio, rounds down, then normalizes using `quoteDecimals`. That order
matters: normalization can amplify the rounding step. The previous candidate
squared the base-token decimal scale before dividing, which matched the initial
fixtures but failed ten of 24 new inverse-price cases. The corrected formula and
these regression cases are included here. Existing target expectations are
unchanged; the evidence manifest was deliberately regenerated for this correction.

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
15 seconds. The quote entry points also check the hard age limit. Their stale-price
fee can differ: a successful 1,000-gas self-call returning exactly 32 bytes enables
using `floor(age * 2 / 5)` for that fee. The public book uses the unscaled age.

The book uses configured `(lot count, spread)` levels. The ask side normally
reserves one lot for a final level with 50,000 additional spread units; a flag can
disable that reserve. Near the inventory boundary, selected levels receive an
additional metadata-controlled penalty. The bid side first checks the inventory
target and quote-token balance, and can include a wide-spread tail sized at five
times the configured inventory target. It then trims the ladder to available
quote funds using the recovered rounding rules. These describe the public book;
trade-update constraints below also determine whether settlement succeeds.

The candidate and captured parent runtimes are both 24,500 bytes. Equality is
established by comparing executable bytes after constructor execution, not by
comparing lengths or counting implemented selectors. The evidence manifest was
deliberately regenerated for this source-fidelity checkpoint. Captured chain
files and behavioral target digests remain unchanged.

## Reconstructed quotes

The four quote modes fill the same ordered liquidity ladder with distinct rounding.
Selling exact input floors quote proceeds per tranche; buying exact output rounds
quote cost up per tranche. The inverse modes use the corresponding base-token
rounding. Exact-output requests return zero when the ladder cannot satisfy them;
internal exact-input fillers saturate at the available ladder. These are quote
calculations, not a proof that a later swap will pass the update checks.

The execution helper builds the ladder, then returns zero for an empty ladder
or a zero requested amount. The public quote path checks for a zero price before
calling this helper. The previous reconstruction incorrectly repeated that price
check inside the helper, diverging in 24 of 128 new direct-entry, zero-price cases;
for example, it returned zero where the original helper reverted with `fee`.
The corrected amount check and regression cases preserve this internal behavior.
These synthetic cases do not demonstrate an externally reachable zero-price swap.
Prior target expectations are unchanged, and the evidence manifest was deliberately
regenerated for this correction.

Ordinary quotes combine a stale-price fee, a caller-class fee, the pool helper,
and a same-block volume fee. There are 44 enum classes, with values above 43 from
the classifier mapped to zero. The analysis does not identify the callers behind
those numbers. Several class branches depend on inventory and trade size; some
also depend on `gasleft()` parity or its remainder modulo five. The tests force
specific GAS results to establish those branches. They do not show that the
candidate consumes the same gas or returns identical quotes at every gas limit.

On chain ID 8453, when prior same-side volume exceeds one lot and the new amount
is nonzero, the volume fee is
`min(ceil((priorVolume - lotSize) / lotSize) * 20, 100)` spread units. A separate
adjustment uses the square of the same-block trade count, subtracting it from
quoted output or adding it to quoted input, only if it is at most one-thousandth
of the amount. These are distinct mechanisms.

A small-trade branch operates only at amounts of at most 16 atomic token units
on the checked side and when the relevant stored counter is at least 16. Its
logarithmic/exponential amount adjustment can bypass the ordinary strict fee
check. That branch records a marker in the quote ID, consumed by `update` as described
below.

Recovered quote-ID additions are:

| Bit offset | Field |
| ---: | --- |
| 112 | Caller class, 8 bits |
| 160 | Stale-price fee, capped at 255 |
| 168 | Caller fee plus helper fee, capped at 255 |
| 176 | Same-block volume fee, capped at 255 |
| 184 | Same-side count, inverted as `255 - count` for asks |
| 192 | Excess inventory / incoming base amount, scaled by 10,000 and capped at 65,535 |
| 208 | Small-trade marker |

The five-byte returned data is derived from the quote ID, block number, timestamp
and caller class. Access tests cover the pricing dispatcher and the special
partner-ID route for direct calls. Update authorization is deliberately different
from quote authorization.

## Reconstructed updates and execution guards

Selector `0x519341bb` accepts a quote ID, arbitrary bytes, a token pair, input and
output amounts, executor, and partner ID. The bytes are ABI-decoded but unused.
Only the pricing dispatcher can call it, and partner IDs 2976/2977 are excluded;
those IDs are allowed as an alternative route for direct quote calls.

A nonzero small-trade marker must be at most 16 and exactly equal the output
amount. The selected side counter must be at least 16; successful processing
subtracts the marker. The base amount must fit uint128. Counts and volume use
checked arithmetic, so overflow reverts rather than wrapping.

The update adds same-side base volume and increments a trade count, plus separate
counts for amounts at least two lots and at least eight lots. It evaluates the
**pre-trade** statistics against these limits:

| Prior statistic | Allowed condition |
| --- | --- |
| Same-side trade count | At most `floor(15 / divisor)` |
| Same-side count of trades at least two lots | At most `floor(10 / divisor)` |
| Trades at least eight lots | Same-side **or** opposite-side prior count at most `floor(5 / divisor)` |

`divisor` is two for reference kinds 3–5 when metadata `raw4` is zero; otherwise
it is one. These are pre-trade checks: with divisor one, a prior count of 15 can
accept another trade. The condition on large trades is not an independent cap
on each side. On Base, statistics are keyed by the current block number.

Transient storage also records the highest sell ratio and lowest buy ratio
within the transaction. Sell ratios use `ceil(output * 1e30 / input)`; buy ratios
use `floor(input * 1e30 / output)`, in raw token units. Each sell must be strictly
below an existing buy bound, and each buy strictly above an existing sell bound.
A sell raises the stored sell bound and a buy lowers the stored buy bound. This
is consistent with preventing crossed round trips within one transaction; that
purpose is an inference, while the strict comparisons and updates are observed.

The owner and four transformed-origin matches bypass the count/ratio guards,
subject to a separate executor/origin allow check, and initialize a transient
price adjustment when it is unset. Partner IDs whose right-shifted value is
`0x90` or `0xca` share the allow check and zero recorded volume, but do **not**
bypass those guards by themselves. All these routes still increment applicable
counts based on the actual base amount. Address-transform matches are recovered
conditions, not attribution of those addresses to particular organizations.

## Validation scope

The parent checkpoint passes 15,451 differential scenarios:

| Scope | Scenarios |
| --- | ---: |
| Constructor metadata and validation | 102 |
| Constructor reference-pool modes | 90 |
| Metadata, administration, authorization and fallback | 234 |
| Price decoding, oracle formats, scaling and arithmetic | 433 |
| Price selection, quote-ID packing and special origins | 1,047 |
| Internal book construction and inventory boundaries | 720 |
| Public book, including one captured RPC result | 58 |
| Four exact-input/exact-output ladder fillers | 2,600 |
| Generalized ladder and caller-class fee rules | 4,560 |
| Amount normalization, volume/count fees and quote-ID fields | 1,548 |
| Small-trade adjustment and strict fee checks | 1,552 |
| Combined internal quote execution, including zero-price entry tests | 1,028 |
| Public quotes, including two captured RPC results | 494 |
| Public updates: accounting, guards, authorization, transient state and ABI | 985 |

Constructor checks compare rejection data, resulting storage and external calls,
excluding the returned child runtime, which is compared separately. State checks
also compare logs. Internal price/book checks seed stack and memory at recovered
entry points in the original runtime and compare them with a test-only Solidity
harness. They are synthetic function experiments, not transaction replays. Public
book checks execute the candidate's actual external entry point and compare full
call trees. Update tests compare rejection bytes, external calls, persistent and
transient storage, and logs, with explicit synthetic pre-trade state. They include
thresholds, dust markers, special routes, alternate block-number paths, invalid
pairs, arbitrary payloads and malformed ABI. They are not historical swap replays.
GAS substitution, alternate chain IDs, and explicitly seeded storage
are controlled experiments. Unlisted dependencies fail closed. No gas-equivalence
or exhaustive-state proof is claimed. The original per-case expected digests are
preserved; added quote groups have target-result digests in
`expected/quote-differential.json`; the update group has its own digest in
`expected/update-differential.json`, with named detailed results written under
`build/elfomofi-engine-checkpoint/`.

`parent-standard-input.json` preserves exact candidate inputs. Both parent and
helper use the stock default optimizer at 100 runs, via IR, targeting Cancun.
The Math library remains unchanged from OpenZeppelin Contracts v4.9.6 under its
MIT license. The parent's inline `fullMulDiv` is an adapted variant with empty
reverts for invalid denominators/overflow and an assembly division fast path;
see [`src/vendor/PROVENANCE.md`](src/vendor/PROVENANCE.md). These dependency choices
do not establish the original imports. Mined selector collisions, including the
two timestamped oracle interfaces, are explicitly marked and independently
hash-checked; they do not recover original function names.

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
