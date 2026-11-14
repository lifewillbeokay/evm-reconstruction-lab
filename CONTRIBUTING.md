# Contributing

Use Python 3.11+ and Node.js 20+. Install locked dependencies with `uv sync
--frozen --extra dev` and `npm ci --ignore-scripts`.

Before submitting changes:

```sh
uv run --frozen pytest -q
uv run --frozen python scripts/evidence.py cases/wintermute-curve-balancer
uv run --frozen python scripts/reproduce.py
uv run --frozen python scripts/evidence.py cases/elfomofi-pricing
uv run --frozen python scripts/reproduce-elfomofi.py
```

Keep RPC credentials and local provider URLs out of commits. Tool tests run
offline; use a deterministic fake RPC rather than a paid endpoint.

For case studies, distinguish observations, inferred semantics, candidate
signatures, and deliberately constructed selector collisions. Include evidence
URLs, compiler provenance, exact input files and documented test limitations.
See [adding cases](docs/adding-cases.md).

Do not silently regenerate an evidence manifest to hide changed case files.
Explain the correction and regenerate it deliberately with `scripts/evidence.py
CASE --write`. Keep exploratory candidates and large compiler IR files under
ignored `build/`, not in the source history.

Scope initial improvements to a demonstrated need in a real case. Additional
compiler versions, proxy families and EVM forks should have targeted fixtures
that fail without the implementation change.

For the live depth app (Node 22.13+; Node 24 recommended):

```sh
cd apps/elfomofi-depth
npm ci
npm test
npm run typecheck
npm run build
```

Its unit tests are offline. The `test:live` script is an explicit public-RPC
collection step and is excluded from CI.
