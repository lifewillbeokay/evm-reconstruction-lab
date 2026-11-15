"""Offline differential experiments for reconstructed quote behavior."""

import json, itertools, random
from price_differential import evaluate, p

ENTRIES = {"sellIn": 0x552C, "sellOut": 0x5470, "buyIn": 0x561F, "buyOut": 0x55A7}


def scenarios():
    out = []
    ladders = [
        [],
        [(10, 1), (20, 100)],
        [(0, 1), (20, 100)],
        [(10, 100000), (20, 50000)],
        [(2**128, 65535)],
    ]
    values = list(
        itertools.product(
            [6, 18, 66, 67],
            [0, 2 * 10**12, 2**256 - 1],
            [0, 1, 9, 10, 11, 29, 30, 31, 60, 2**256 - 1],
            ladders,
        )
    )
    rng = random.Random(8453)
    for i in range(50):
        values.append(
            (
                rng.choice([6, 8, 18]),
                rng.randrange(10**9, 10**16),
                rng.randrange(1, 10**20),
                [
                    (rng.randrange(0, 10**20), rng.randrange(1000))
                    for _ in range(rng.randrange(1, 8))
                ],
            )
        )
    for i, (decimals, price, amount, levels) in enumerate(values):
        words = {1024: len(levels)}
        for j, (capacity, spread) in enumerate(levels):
            words[1056 + j * 32] = 1536 + j * 64
            words[1536 + j * 64] = capacity
            words[1568 + j * 64] = spread
        for name, entry in ENTRIES.items():
            out.append(
                (
                    f"{name}-{i}",
                    (
                        entry,
                        [decimals, price, amount, 1024],
                        words,
                        name,
                        ["uint8", "uint256", "uint256", "(uint256,uint256)[]"],
                        [decimals, price, amount, levels],
                        "scalar",
                    ),
                    {},
                )
            )
    return out


if __name__ == "__main__":
    results = []
    for name, args, kwargs in scenarios():
        results.append({"name": name, **evaluate(*args, **kwargs)})
    (p.BUILD / "fill-differential.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "cases": len(results),
                "matched": sum(r["match"] for r in results),
                "failures": [r for r in results if not r["match"]],
            }
        )
    )
