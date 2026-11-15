"""Offline differential experiments for reconstructed quote behavior."""

import json, copy, itertools, random
from eth_abi import encode
from eth_utils import keccak
from internal_probe import probe, p
from reference_constructor_probe import responder

A = json.loads((p.BUILD / "state-compiled.json").read_text())
_, _, _, _, created = p.run(
    p.ARGS, creation=bytes.fromhex(A["evm"]["bytecode"]["object"])
)
assert not created.is_error
RUNTIME = "0x" + created.output.hex()
T = p.ARGS[4][0]
Q = p.ARGS[2]
NOW = int(p.HEADER["timestamp"], 16)
KEY = "0x" + keccak(encode(["address", "uint256"], [T, 1])).hex()


def evaluate(data, **kwargs):
    target, _, _ = probe(data=data, trace=False, **kwargs)
    codes = {**kwargs.pop("code", {}), p.ENGINE: RUNTIME}
    candidate, _, _ = probe(data=data, trace=False, code=codes, **kwargs)

    def tree(c):
        return {
            "to": c.msg.to.hex(),
            "data": c.msg.data_as_bytes.hex(),
            "error": c.is_error,
            "output": c.output.hex(),
            "children": [tree(x) for x in c.children],
        }

    tc = [tree(c) for c in target.children]
    cc = [tree(c) for c in candidate.children]
    return {
        "match": target.is_error == candidate.is_error
        and target.output == candidate.output
        and tc == cc,
        "calls_match": tc == cc,
        "target_error": target.is_error,
        "candidate_error": candidate.is_error,
        "target": target.output.hex(),
        "candidate": candidate.output.hex(),
        **({"target_calls": tc, "candidate_calls": cc} if tc != cc else {}),
    }


def scenarios():
    out = []
    for row in json.loads((p.CASE / "evidence/baseline-replays.json").read_text()):
        if row["name"].startswith(("sell", "buy")):
            out.append((row["name"], bytes.fromhex(row["data"][2:]), {}))
    for exact, ask, amount in itertools.product(
        [False, True],
        [False, True],
        [0, 1, 15, 16, 17, 10**6, 10**10, 10**16, 10**18, 10**20],
    ):
        sig = (
            "getAmount"
            + ("Out" if exact else "In")
            + "(address,address,uint256,address,uint256)"
        )
        a, b = (Q, T) if ask else (T, Q)
        data = keccak(text=sig)[:4] + encode(
            ["address", "address", "uint256", "address", "uint256"],
            [a, b, amount, p.ARGS[0], 0],
        )
        out.append(
            (
                f"full-{exact}-{ask}-{amount}",
                data,
                {"synthetic_storage": {p.ENGINE: {KEY: "0x0"}}},
            )
        )
    witness = json.loads((p.CASE / "evidence/state-witness-getters.json").read_text())
    posted = int(witness[p.ENGINE]["storage"]["0x2"], 16)
    rows = list(
        itertools.product(
            [False, True],
            [False, True],
            [0, 7, 23, 43, 44, 255, 256],
            [0, 7, 11, 16],
            [0, 10**18, 90 * 10**18],
            [p.ARGS[0], p.DEPLOYER, "0x" + "12" * 20],
        )
    )
    rng = random.Random(8453)
    rng.shuffle(rows)
    for i, (exact, ask, kind, age, balance, origin) in enumerate(rows[:420]):
        sig = (
            "getAmount"
            + ("Out" if exact else "In")
            + "(address,address,uint256,address,uint256)"
        )
        a, b = (Q, T) if ask else (T, Q)
        amount = 10**16 if ask != exact else 10**7
        data = keccak(text=sig)[:4] + encode(
            ["address", "address", "uint256", "address", "uint256"],
            [a, b, amount, "0x" + "34" * 20, 0],
        )
        codes = {
            p.ARGS[0]: responder({"725e6ced": encode(["uint256"], [kind])}),
            T: responder({"70a08231": encode(["uint256"], [balance])}),
        }
        out.append(
            (
                f"controlled-{i}-{exact}-{ask}-{kind}-{age}-{balance}-{origin}",
                data,
                {
                    "origin": origin,
                    "gas_value": 1000000,
                    "code": codes,
                    "overrides": {
                        p.ENGINE: {"0x2": hex((posted & ~(2**32 - 1)) | (NOW - age))}
                    },
                    "synthetic_storage": {p.ENGINE: {KEY: "0x0"}},
                },
            )
        )
    for exact, sender, partner, invalid_pair in itertools.product(
        [False, True],
        [p.ARGS[0], "0x" + "12" * 20],
        [2975, 2976, 2977, 2978],
        [False, True],
    ):
        sig = (
            "getAmount"
            + ("Out" if exact else "In")
            + "(address,address,uint256,address,uint256)"
        )
        data = keccak(text=sig)[:4] + encode(
            ["address", "address", "uint256", "address", "uint256"],
            [T, T if invalid_pair else Q, 10**16, p.ARGS[0], partner],
        )
        out.append(
            (
                f"access-{exact}-{sender}-{partner}-{invalid_pair}",
                data,
                {"sender": sender},
            )
        )
    return out


if __name__ == "__main__":
    results = []
    for name, data, kwargs in scenarios():
        results.append({"name": name, **evaluate(data, **kwargs)})
    (p.BUILD / "full-quote-differential.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    summary = {
        "cases": len(results),
        "matched": sum(r["match"] for r in results),
        "failures": [r for r in results if not r["match"]],
    }
    (p.BUILD / "full-quote-differential-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps({**summary, "failures": summary["failures"][:5]}))
