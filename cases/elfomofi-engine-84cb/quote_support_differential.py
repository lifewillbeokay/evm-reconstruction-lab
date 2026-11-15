"""Offline differential experiments for reconstructed quote behavior."""

import copy, json, itertools
from price_differential import evaluate, p, mw
import book_differential as books


def scenarios():
    out = []
    for name, args, kwargs in books.scenarios():
        entry, stack, words, fn, types, values, outputs = args
        ask = fn == "asks"
        for suppress in [False, True]:
            out.append(
                (
                    f"generic-{name}-{suppress}",
                    (
                        0x353E,
                        [int(suppress), int(ask)] + stack,
                        words,
                        "quoteBook",
                        ["bool", "bool"] + types,
                        [suppress, ask] + values,
                        outputs,
                    ),
                    kwargs,
                )
            )
    m = copy.deepcopy(p.ARGS[5][0])
    m[7] = 10
    m[8] = 15
    m[9] = 3

    def add(name, kind, ask, age, amount, balance, chain, gas, metadata=m):
        out.append(
            (
                name,
                (
                    0x4E10,
                    [amount, balance, 128, int(ask), age, kind],
                    mw(metadata),
                    "feeClass",
                    ["uint256", "uint256", p.META_TYPE, "bool", "uint256", "uint256"],
                    [amount, balance, metadata, ask, age, kind],
                    "scalar",
                ),
                {"chain_id": chain, "gas_value": gas},
            )
        )

    for chain, kind, ask, age, gas in itertools.product(
        [8453, 56, 4663], range(45), [False, True], [0, 2], [0, 1, 2, 5]
    ):
        add(f"fee-{chain}-{kind}-{ask}-{age}-{gas}", kind, ask, age, 10, 50, chain, gas)
    for kind, ask, amount, balance, gas in itertools.product(
        [6, 7, 13, 40],
        [False, True],
        [0, 4, 5, 39, 40, 41],
        [0, 30, 31, 119, 120, 150],
        [0, 1, 5],
    ):
        add(
            f"fee-edge-{kind}-{ask}-{amount}-{balance}-{gas}",
            kind,
            ask,
            2,
            amount,
            balance,
            4663,
            gas,
        )
    for kind, ask, age, lot in itertools.product(
        [0, 1, 6, 23, 26, 44], [False, True], [0, 2], [0, 1, 2, 2**128 - 1]
    ):
        metadata = copy.deepcopy(m)
        metadata[7] = lot
        add(
            f"fee-overflow-{kind}-{ask}-{age}-{lot}",
            kind,
            ask,
            age,
            2**256 - 1,
            2**256 - 1,
            8453,
            5,
            metadata,
        )
    return out


if __name__ == "__main__":
    results = []
    for name, args, kwargs in scenarios():
        results.append({"name": name, **evaluate(*args, **kwargs)})
    (p.BUILD / "quote-support-differential.json").write_text(
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
