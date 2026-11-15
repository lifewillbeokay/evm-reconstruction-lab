"""Offline differential experiments for reconstructed quote behavior."""

import itertools, json, random
from eth_abi import encode
from eth_utils import keccak
from price_differential import evaluate, p

TOKEN = p.ARGS[4][0]
KEY = "0x" + keccak(encode(["address", "uint256"], [TOKEN, 1])).hex()


def scenarios():
    out = []
    for ask, exact, amount, price, result in itertools.product(
        [False, True],
        [False, True],
        [0, 1, 3, 10],
        [0, 25 * 10**11],
        [0, 1, 2, 3, 7, 8, 9, 10, 24, 25, 26],
    ):
        vals = [ask, 6, price, exact, result, amount]
        out.append(
            (
                f"fee-{ask}-{exact}-{amount}-{price}-{result}",
                (
                    0x5898,
                    [int(ask), 6, price, int(exact), result, amount],
                    {},
                    "feeCheck",
                    ["bool", "uint8", "uint256", "bool", "uint256", "uint256"],
                    vals,
                    [],
                ),
                {},
            )
        )
    values = list(
        itertools.product(
            [False, True],
            [False, True],
            [0, 6, 8, 18],
            [0, 1, 2, 3, 15, 16, 17, 100],
            [0, 1, 2, 15, 16, 17],
            [0, 15, 16, 65535],
        )
    )
    rng = random.Random(5600)
    rng.shuffle(values)
    values = values[:1200]
    for i, (ask, exact, dec, amount, result, counter) in enumerate(values):
        amount = amount * 10 ** (max(dec - 7, 0)) if exact and i % 2 else amount
        price = rng.choice([0, 25 * 10**11, 2**256 - 1])
        levels = rng.choice(
            [[], [(0, 1)], [(15, 1)], [(16, 1)], [(10**18, 10)], [(10**25, 100001)]]
        )
        words = {1024: len(levels)}
        for j, (cap, spread) in enumerate(levels):
            words[1056 + j * 32] = 1536 + j * 64
            words[1536 + j * 64] = cap
            words[1568 + j * 64] = spread
        packed = (counter if i % 2 else 0) + ((counter if not i % 2 else 0) << 16)
        vals = [ask, TOKEN, price, exact, result, amount, dec, levels]
        out.append(
            (
                f"small-{i}-{ask}-{exact}-{dec}-{amount}-{result}-{packed}-{price}-{levels}",
                (
                    0x56BD,
                    [
                        int(ask),
                        int(TOKEN, 16),
                        price,
                        int(exact),
                        result,
                        amount,
                        dec,
                        1024,
                    ],
                    words,
                    "smallTrade",
                    [
                        "bool",
                        "address",
                        "uint256",
                        "bool",
                        "uint256",
                        "uint256",
                        "uint8",
                        "(uint256,uint256)[]",
                    ],
                    vals,
                    ["uint256"] * 2,
                ),
                {"synthetic_storage": {p.ENGINE: {KEY: hex(packed)}}},
            )
        )
    return out


if __name__ == "__main__":
    results = []
    for name, args, kwargs in scenarios():
        results.append({"name": name, **evaluate(*args, **kwargs)})
    (p.BUILD / "small-trade-differential.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    summary = {
        "cases": len(results),
        "matched": sum(r["match"] for r in results),
        "failures": [r for r in results if not r["match"]],
    }
    (p.BUILD / "small-trade-differential-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps({**summary, "failures": summary["failures"][:8]}))
