# ElfomoFi Depth Lab

A live, read-only virtual order book for WETH/USDC, cbBTC/USDC and AAPLc/USDC on Base.
The hosted version uses Vinext and React on a Cloudflare Worker through Sites.
This portable copy runs the same UI and adapter with Next.js. Site identity and credentials are not included.

Live site: https://elfomofi-depth-lab.jersey.chatgpt.site (owner-private; ChatGPT sign-in).

## Run

Use Node 22.13+ (Node 24 recommended), then `npm install` and `npm run dev`.
Run the offline regression suite with `node --experimental-strip-types --test tests/*.test.ts`.
Run `npx tsc --noEmit` for type checking. `npm run build` produces a Next.js production build; `npm start` serves it.
With a local server running, `node scripts/smoke.mjs http://localhost:3000` performs explicit live RPC validation.

## Data contract

`GET /api/book?market=WETH&executor=0x1111111111111111111111111111111111111111&partner=0`
accepts an optional decimal `size` in base tokens. It reads Base using PublicNode,
with dRPC, Automata 1RPC and the official Base public RPC as fallbacks. No keys, wallet, writes, or
transaction broadcasting are required. The page collects directly from browser-accessible public RPCs first, avoiding shared hosting IP quotas. The same collector is available through the hosted API as a fallback; that API may be rate limited independently. Public RPC services are best effort and
rate limited; this is a research dashboard, with 15-second foreground refresh,
12-second request coalescing, 32-key bounded cache and explicit stale/error states.

Every call is pinned to one block number, and the canonical block hash is checked
again after the sweep. Each quote is an independent `eth_call` to the pricing proxy
from the swap wrapper with 30M gas, 1 wei gas price, and the visible executor and
partner context. Sells use `getAmountOut(base, USDC, size, executor, partner)`;
buys use `getAmountIn(USDC, base, size, executor, partner)`.

Quote-derived intervals use delta quote / delta base quantity. They are estimates
between samples, not continuously known marginal prices. The curve preserves fill
order and stops at the first failed, zero, or non-increasing quote. It never
interpolates unavailable depth. The separate engine-ladder view has incremental
capacities and 1e12-scaled USDC prices; it excludes some caller adjustments.
Charts use floating point for display. Exports preserve raw integer quote values,
quantities, quote IDs, caller parameters, block number and block hash.

The route is read from dispatcher storage at every snapshot. The adapter pauses
if the dispatcher implementation changes. Unreviewed engine addresses retain
quote-derived depth but have ladder decoding disabled. Raw storage slot 2 is
decoded only for the two reviewed engines; new engine layouts need review.

## Execution simulator and architecture

The Execution tab calls the original deployed engine with a read-only RPC probe.
It runs a quote followed by `update` in the same `eth_call` and distinguishes a
passing engine check, absent quote, reverted quote, failed execution guard, and
RPC failure. It does not run token transfers, approvals, the original dispatcher
or full swap settlement. Independent sizes do not consume one another's liquidity.

Controls cover 44 caller classes, up to 16 base-token sizes, posted-price age,
same-block volume/counts, large-trade counters and gas/access context. Scenarios
remain pinned to the same block while comparing settings; New snapshot refreshes
it. Engine and helper code hashes plus pair routing are checked. Age and flow
overrides are explicit, with raw inputs/results and hashes in the JSON export.
The classifier response is synthetic; class numbers are not named trader identities.

`POST /api/simulate` accepts the `Scenario` shape in `lib/simulation.ts`. The browser
tries public RPC directly first, then uses this same collector through the API.
No wallet, transaction signing, deployment or chain writes are involved.

The Architecture tab visualizes the full pricing process and links to the
[case architecture](../../cases/elfomofi-engine-84cb/ARCHITECTURE.md). It distinguishes
observed rules from inferred trading intent and unrecovered offchain strategy.

The earlier case preserves `0xd6ac027dbcbf19489e8ecd4d719aa83396eca3ee`. The current
`0x84cb1a96e57e9b88cf75035384c06dc3769654ae` engine and its fee helper now have verified
reconstructed source on Basescan. Both runtime executables and the entire creation
executable match; original metadata hashes differ. Storage slot 2 is reviewed for
both engines. The new execution probe supports only the verified current runtime.

Build/check the instrumentation from the repository root:

```sh
node scripts/build-execution-probe.cjs
node scripts/build-execution-probe.cjs --check
```

Explicit RPC integration checks (not part of offline CI):

```sh
node --experimental-strip-types scripts/simulate-live.mjs
```

This checks a pinned block for class fees, age penalties, cold/warm fee context,
expiry, pre-trade count boundaries and the two-sided large-trade guard, then checks
current WETH/cbBTC/AAPLc routing. Offline tests cover code fingerprints, mapping
slots, state overrides, ABI/revert decoding, route changes and reorg rejection.
The fixture bytecode is copied from the preserved case evidence.

## References

- https://docs.elfomo.fi/
- https://github.com/lifewillbeokay/evm-reconstruction-lab/tree/main/cases/elfomofi-pricing
- https://github.com/ElfomoFi/elfomofi-sdk
- https://hyperscreener.asxn.xyz/liquidity-comparison (visual reference)
- https://docs.base.org/get-started/connect-to-base
- https://base.publicnode.com/

Additional provider documentation: https://drpc.org/docs/base-api and https://docs.1rpc.io/overview/supported-networks.
