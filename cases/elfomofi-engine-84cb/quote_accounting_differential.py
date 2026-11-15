"""Offline differential experiments for reconstructed quote behavior."""

import copy, itertools, json
from eth_abi import encode
from eth_utils import keccak
from price_differential import evaluate, p, mw
from reference_constructor_probe import responder

TOKEN = p.ARGS[4][0]
BLOCK = int(p.HEADER["number"], 16)
HELPER = "0x42e88fbc20c66bfe4bac17892980b640990d8cbc"


def stat_key(ask):
    return (
        "0x"
        + keccak(
            encode(
                ["uint256", "bytes32"],
                [BLOCK, keccak(encode(["address", "uint256"], [TOKEN, 3 + ask]))],
            )
        ).hex()
    )


def scenarios():
    out = []

    def add(name, entry, args, words, fn, types, values, outputs="scalar", **kwargs):
        out.append((name, (entry, args, words, fn, types, values, outputs), kwargs))

    for ask, exact, dec, amount, price in itertools.product(
        [False, True],
        [False, True],
        [0, 6, 18, 77, 78],
        [0, 1, 9, 20, 2**256 - 1],
        [0, 3 * 10**12],
    ):
        m = copy.deepcopy(p.ARGS[5][0])
        m[1] = dec
        add(
            f"normalize-{ask}-{exact}-{dec}-{amount}-{price}",
            0x4CDB,
            [int(ask), price, int(exact), amount, 128],
            mw(m),
            "normalize",
            ["bool", "uint256", "bool", "uint256", p.META_TYPE],
            [ask, price, exact, amount, m],
        )
    for ask, lot, amount, volume, count, chain in itertools.product(
        [False, True],
        [0, 1, 10, 11],
        [0, 1, 20],
        [0, 10, 11, 40, 100],
        [0, 3, 255],
        [8453, 56],
    ):
        add(
            f"volume-{ask}-{lot}-{amount}-{volume}-{count}-{chain}",
            0x4D4C,
            [int(ask), lot, amount, int(TOKEN, 16)],
            {},
            "volumeFee",
            ["bool", "uint128", "uint256", "address"],
            [ask, lot, amount, TOKEN],
            ["uint256"] * 2,
            chain_id=chain,
            overrides={p.ENGINE: {stat_key(ask): hex(volume + (count << 128))}},
        )
    for ask, subtract, amount, count in itertools.product(
        [False, True],
        [False, True],
        [0, 1, 8999, 9000, 9001, 65025000, 2**256 - 1],
        [0, 3, 255],
    ):
        add(
            f"count-{ask}-{subtract}-{amount}-{count}",
            0x3D9B,
            [int(ask), int(TOKEN, 16), int(subtract), amount],
            {},
            "countAdjust",
            ["bool", "address", "bool", "uint256"],
            [ask, TOKEN, subtract, amount],
            overrides={p.ENGINE: {stat_key(ask): hex(count << 128)}},
        )
    for amount, balance, lot, maximum, qid in itertools.product(
        [0, 1, 20, 2**256 - 1],
        [0, 10, 149, 150, 151],
        [0, 10],
        [0, 15],
        [0, 2**256 - 1],
    ):
        m = copy.deepcopy(p.ARGS[5][0])
        m[7] = lot
        m[8] = maximum
        add(
            f"inventory-{amount}-{balance}-{lot}-{maximum}-{qid}",
            0x5936,
            [amount, balance, 128, qid],
            mw(m),
            "inventory",
            ["uint256", "uint256", p.META_TYPE, "uint256"],
            [amount, balance, m, qid],
        )
    m = copy.deepcopy(p.ARGS[5][0])
    m[1] = 6
    m[7] = 10
    m[8] = 15
    m[9] = 3
    for ask, exact, discount, age, kind, helper in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [0, 6, 7, 11],
        [0, 7, 23],
        [0, 17, 1000, 1001],
    ):
        vals = [ask, 3 * 10**12, exact, 21, discount, age, 50, kind, m, TOKEN, 0]
        args = [
            int(ask),
            vals[1],
            int(exact),
            21,
            int(discount),
            age,
            50,
            kind,
            128,
            int(TOKEN, 16),
            0,
        ]
        add(
            f"projection-{ask}-{exact}-{discount}-{age}-{kind}-{helper}",
            0x3AF2,
            args,
            mw(m),
            "projection",
            [
                "bool",
                "uint256",
                "bool",
                "uint256",
                "bool",
                "uint256",
                "uint256",
                "uint256",
                p.META_TYPE,
                "address",
                "uint256",
            ],
            vals,
            ["uint256"] * 2,
            gas_value=1000000,
            overrides={p.ENGINE: {stat_key(ask): hex(40 + (3 << 128))}},
            code={HELPER: responder({"b88c9148": encode(["uint256"], [helper])})},
        )
    return out


if __name__ == "__main__":
    results = []
    for name, args, kwargs in scenarios():
        results.append({"name": name, **evaluate(*args, **kwargs)})
    (p.BUILD / "quote-accounting-differential.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    summary = {
        "cases": len(results),
        "matched": sum(r["match"] for r in results),
        "failures": [r for r in results if not r["match"]],
    }
    (p.BUILD / "quote-accounting-differential-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps({**summary, "failures": summary["failures"][:5]}))
