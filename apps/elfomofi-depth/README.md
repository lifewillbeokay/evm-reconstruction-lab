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
decoded for price age only on the previously studied engine; it is not assumed
to have the same layout on newly routed engines.

## Reconstruction and verification

The historical case study in `lifewillbeokay/evm-reconstruction-lab` concerns
engine `0xd6ac027dbcbf19489e8ecd4d719aa83396eca3ee`. During live development on
2026-11-14 the dispatcher routed all three displayed pairs to
`0x84cb1a96e57e9b88cf75035384c06dc3769654ae` (24,500 runtime bytes).
The current engine was unverified on Basescan when checked. This site uses
original deployed bytecode and public call interfaces. No matching full-source
reconstruction exists yet, and no source verification was submitted for this site.

## References

- https://docs.elfomo.fi/
- https://github.com/lifewillbeokay/evm-reconstruction-lab/tree/main/cases/elfomofi-pricing
- https://github.com/ElfomoFi/elfomofi-sdk
- https://hyperscreener.asxn.xyz/liquidity-comparison (visual reference)
- https://docs.base.org/get-started/connect-to-base
- https://base.publicnode.com/

Additional provider documentation: https://drpc.org/docs/base-api and https://docs.1rpc.io/overview/supported-networks.
