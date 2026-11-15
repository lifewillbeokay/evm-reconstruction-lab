"""Offline differential experiments for reconstructed quote behavior."""

import copy, json, itertools, random
from eth_abi import encode
from eth_utils import keccak
from price_differential import evaluate, p, mw
from reference_constructor_probe import responder

T = p.ARGS[4][0]
KEY = "0x" + keccak(encode(["address", "uint256"], [T, 1])).hex()


def scenarios():
    out = []
    m = copy.deepcopy(p.ARGS[5][0])
    m[1] = 6
    m[7] = 10
    m[8] = 15
    m[9] = 3
    slot = hex(int.from_bytes(keccak(bytes(64)), "big"))
    word = (
        3 | ((2 | (3 << 16)) << 8) | ((5 | (7 << 16)) << 40) | ((10 | (12 << 16)) << 72)
    )
    rows = list(
        itertools.product(
            [False, True],
            [False, True],
            [False, True],
            [0, 1, 10, 11, 25, 100, 151, 10000],
            [0, 1, 50000],
            [0, 10, 100, 150],
            [0, 16],
        )
    )
    rng = random.Random(323)
    rng.shuffle(rows)
    for i, (suppress, ask, exact, amount, extra, balance, counter) in enumerate(
        rows[:900]
    ):
        price = 25 * 10**11
        quoteId = i
        kwargs = {
            "code": {
                T: responder({"70a08231": encode(["uint256"], [balance])}),
                p.ARGS[2]: responder({"70a08231": encode(["uint256"], [10000])}),
            },
            "overrides": {p.ENGINE: {slot: hex(word)}},
            "synthetic_storage": {p.ENGINE: {KEY: hex(counter + (counter << 16))}},
        }
        vals = [suppress, ask, T, extra, price, exact, amount, quoteId, m]
        args = [
            int(suppress),
            int(ask),
            int(T, 16),
            extra,
            price,
            int(exact),
            amount,
            quoteId,
            128,
        ]
        out.append(
            (
                f"execute-{i}-{suppress}-{ask}-{exact}-{amount}-{extra}-{balance}-{counter}",
                (
                    0x3BD4,
                    args,
                    mw(m),
                    "execute",
                    [
                        "bool",
                        "bool",
                        "address",
                        "uint256",
                        "uint256",
                        "bool",
                        "uint256",
                        "uint256",
                        p.META_TYPE,
                    ],
                    vals,
                    ["uint256"] * 2,
                ),
                kwargs,
            )
        )
    # These probe the internal execution entry directly. The public quote path
    # has a separate zero-price guard before it reaches this routine. The
    # deployed routine at 0x3bd4 instead checks amount == 0 after building levels.
    # Replacing that check with price == 0 incorrectly bypasses fills, dust
    # adjustment and fee validation in these otherwise unreachable inputs.
    for suppress, ask, exact, amount, balance, counter in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [0, 1, 16, 100],
        [10, 100],
        [0, 16],
    ):
        kwargs = {
            "code": {
                T: responder({"70a08231": encode(["uint256"], [balance])}),
                p.ARGS[2]: responder({"70a08231": encode(["uint256"], [10000])}),
            },
            "overrides": {p.ENGINE: {slot: hex(word)}},
            "synthetic_storage": {p.ENGINE: {KEY: hex(counter + (counter << 16))}},
        }
        out.append(
            (
                f"execute-zero-price-{suppress}-{ask}-{exact}-{amount}-{balance}-{counter}",
                (
                    0x3BD4,
                    [
                        int(suppress),
                        int(ask),
                        int(T, 16),
                        0,
                        0,
                        int(exact),
                        amount,
                        77,
                        128,
                    ],
                    mw(m),
                    "execute",
                    [
                        "bool",
                        "bool",
                        "address",
                        "uint256",
                        "uint256",
                        "bool",
                        "uint256",
                        "uint256",
                        p.META_TYPE,
                    ],
                    [suppress, ask, T, 0, 0, exact, amount, 77, m],
                    ["uint256"] * 2,
                ),
                kwargs,
            )
        )
    return out


if __name__ == "__main__":
    results = []
    for name, args, kwargs in scenarios():
        results.append({"name": name, **evaluate(*args, **kwargs)})
    (p.BUILD / "execute-differential.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    summary = {
        "cases": len(results),
        "matched": sum(r["match"] for r in results),
        "failures": [r for r in results if not r["match"]],
    }
    (p.BUILD / "execute-differential-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps({**summary, "failures": summary["failures"][:5]}))
