# Optional Apple Metal selector miner

The first case used a GPU search to find synthetic Solidity names with specified
four-byte selectors. `mine-selectors.swift` preserves that technique as a bounded,
resumable utility. It requires macOS, Swift and a Metal-capable GPU. The Python
miner is portable but much slower; GPU code is not part of the Linux CI job.

```sh
swiftc -O tools/mine-selectors.swift -o tools/mine-selectors
mkdir -p build/mining
```

Write a job file under `build/mining/jobs.json`:

```json
[{"suffix":"(address)","targets":["12345678"],"offset":0}]
```

The target is an eight-digit hexadecimal selector without `0x`. The suffix is
the full canonical argument list, including parentheses. Each job supports up
to 20 targets sharing that argument list and up to 113 ASCII suffix bytes.

```sh
# At most 20 batches of 1,048,576 candidates. Re-run to resume.
tools/mine-selectors build/mining/jobs.json build/mining/found.json 20
uv run python scripts/check-selector-hits.py build/mining/found.json
```

The miner updates both files atomically, saves hits before advancing offsets,
and stops at the requested batch limit. Exit 0 means the bounded run completed,
not that every target was found. Do not run multiple processes against the same
files. Targets already present in the results file are skipped; verify existing
results before resuming and use new files for unrelated jobs.

Names use a fixed `recovered_` prefix followed by 12 least-significant-first
base-32 characters (`0-9a-v`). This enumerator differs from the portable Python
miner's decimal names. The search is limited to a 60-bit counter and a single
Keccak rate block. Large searches can take substantial time and GPU resources.

**A synthetic collision is not an original name recovery.** Always verify hits
independently with Ethereum Keccak and record their provenance. All 17 signatures
in the first case are checked by the test suite without repeating the search.
