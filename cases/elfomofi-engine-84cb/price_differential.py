import copy, json, random
from eth_abi import encode
from eth_utils import keccak
from internal_probe import probe, p
from reference_constructor_probe import responder, POOL

M = p.ARGS[5][0]
NOW = int(p.HEADER["timestamp"], 16)
ARTIFACT = json.loads((p.BUILD / "price-harness-compiled.json").read_text())
_, _, _, _, created = p.run(
    p.ARGS, creation=bytes.fromhex(ARTIFACT["evm"]["bytecode"]["object"])
)
assert not created.is_error
RUNTIME = "0x" + created.output.hex()


def iv(v):
    return v if isinstance(v, int) else int.from_bytes(v, "big")


def mw(m):
    return {
        128 + 32 * i: int(x, 16) if isinstance(x, str) else x for i, x in enumerate(m)
    }


def evaluate(entry, args, words, fn, types, values, outputs, **kwargs):
    target, _, _ = probe(entry, [0xE] + args, words, trace=False, **kwargs)
    overrides = {**kwargs.pop("code", {}), p.ENGINE: RUNTIME}
    candidate, _, _ = probe(
        data=keccak(text=fn + "(" + ",".join(types) + ")")[:4] + encode(types, values),
        code=overrides,
        trace=False,
        **kwargs,
    )
    if target.is_error:
        a = target.output
    elif outputs == "scalar":
        a = encode(["uint256"], [iv(target._stack.values[-1])])
    elif isinstance(outputs, int):
        ptr = iv(target._stack.values[-1])
        a = target.memory_read_bytes(ptr, 32 * outputs)
    elif outputs == "levels":
        ptr = iv(target._stack.values[-1])
        n = iv(target.memory_read_bytes(ptr, 32))
        rows = []
        for i in range(n):
            at = iv(target.memory_read_bytes(ptr + 32 * (i + 1), 32))
            rows.append(
                tuple(iv(target.memory_read_bytes(at + j * 32, 32)) for j in range(2))
            )
        a = encode(["(uint256,uint256)[]"], [rows])
    else:
        a = encode(
            ["uint256"] * len(outputs),
            [iv(x) for x in target._stack.values[-len(outputs) :]],
        )

    def tree(c):
        return {
            "to": c.msg.to.hex(),
            "data": c.msg.data_as_bytes.hex(),
            "error": c.is_error,
            "output": c.output.hex(),
            "children": [tree(x) for x in c.children],
        }

    target_calls = [tree(c) for c in target.children]
    candidate_calls = [tree(c) for c in candidate.children]
    return {
        "match": target.is_error == candidate.is_error
        and a == candidate.output
        and target_calls == candidate_calls,
        "calls_match": target_calls == candidate_calls,
        "target_error": target.is_error,
        "candidate_error": candidate.is_error,
        "target": a.hex(),
        "candidate": candidate.output.hex(),
    }


def scenarios():
    out = []

    def add(name, *args, **kw):
        out.append((name, args, kw))

    for index in [0, 1, 2, 7, 8, 255]:
        for dec in [0, 2, 12, 13]:
            for shift in [0, 1, 31, 32, 63]:
                m = copy.deepcopy(M)
                m[0] = index
                m[2] = dec
                word = (
                    ((123456 + (shift << 22)) << (32 + 28 * min(index, 7))) + (NOW - 4)
                ) % (1 << 256)
                add(
                    f"posted-{index}-{dec}-{shift}",
                    0x3E04,
                    [128],
                    mw(m),
                    "posted",
                    [p.META_TYPE],
                    [m],
                    4,
                    overrides={p.ENGINE: {"0x2": hex(word)}},
                )
    for time in [0, NOW - 100, NOW, NOW + 1, 2**32 - 1]:
        add(
            f"posted-time-{time}",
            0x3E04,
            [128],
            mw(M),
            "posted",
            [p.META_TYPE],
            [M],
            4,
            overrides={p.ENGINE: {"0x2": hex((123456 << 32) + time)}},
        )
    for age in list(range(17)) + [100, 2**256 - 1]:
        add(f"age-{age}", 0x2FC5, [age], {}, "age", ["uint256"], [age], "scalar")
    for adj in [
        -(2**255),
        -100001,
        -100000,
        -99999,
        -50,
        -32,
        -1,
        0,
        1,
        31,
        50,
        100000,
        2**255 - 1,
    ]:
        for price in [0, 1, 100001, 2**256 - 1]:
            add(
                f"adjust-{adj}-{price}",
                0x4446,
                [adj, price],
                {},
                "adjust",
                ["int256", "uint256"],
                [adj, price],
                "scalar",
            )
    for a, b in [
        (0, 0),
        (0, 1),
        (1, 0),
        (100, 99),
        (100, 101),
        (100, 102),
        (100, 200),
        (200, 100),
        (2**256 - 1, 1),
    ]:
        for t in [0, 1, 100, 5000, 10000]:
            add(
                f"deviation-{a}-{b}-{t}",
                0x4391,
                [t, a, b],
                {},
                "deviation",
                ["uint256"] * 3,
                [t, a, b],
                "scalar",
            )
    for sqrt in [0, 1, 2**96 - 1, 2**96, 2**128 - 1, 2**128, 2**160 - 1]:
        for dec in [0, 6, 8, 18, 77, 78, 255]:
            add(
                f"sqrt-{sqrt}-{dec}",
                0x5E1D,
                [dec, sqrt],
                {},
                "sqrtPrice",
                ["uint160", "uint8"],
                [sqrt, dec],
                "scalar",
            )
    for kind in [0, 1, 2, 3, 4, 5, 6]:
        for variant in [
            "normal",
            "zero",
            "short",
            "revert",
            "no-code",
            "old-44",
            "old-45",
            "old-119",
            "old-120",
            "future",
            "invalid-fields",
            "sqrt-one",
            "sqrt-max",
            "reverse",
            "invalid-aux",
            "dec-6",
            "dec-78",
        ]:
            m = copy.deepcopy(M)
            m[3] = kind
            m[4] = 3
            m[6] = 5
            m[11] = POOL
            m[12] = 1
            age = 7 if not variant.startswith("old-") else int(variant[4:])
            time = NOW - age
            if variant == "future":
                time = NOW + 100
            price = 174425530000
            sqrt = 2**96
            if variant == "zero":
                price = sqrt = 0
            if variant == "sqrt-one":
                sqrt = 1
            if variant == "sqrt-max":
                sqrt = 2**160 - 1
            if variant == "reverse":
                m[12] = 2
            if variant == "invalid-aux":
                m[12] = 3
            if variant == "dec-6":
                m[1] = 6
            if variant == "dec-78":
                m[1] = 78
            responses = {
                "b80777ea": encode(["uint256"], [time]),
                "c6ddb642": encode(["uint256"] * 3, [price, 0, 0]),
                "b5e4b813": encode(["uint256"] * 4, [price, 0, 0, time * 1000]),
                "3850c7bd": encode(["uint256"], [sqrt]),
                "1e2eaeaf": encode(["uint256"], [sqrt]),
            }
            if variant == "invalid-fields":
                responses["c6ddb642"] = encode(["uint256"] * 3, [price, 1 << 64, 0])
                responses["b5e4b813"] = encode(
                    ["uint256"] * 4, [price, 1 << 16, 0, time * 1000]
                )
            if variant == "short":
                responses = {key: b"\x01" for key in responses}
            code = responder(responses)
            if variant == "revert":
                code = "0x63deadbeef5f5260205ffd"
            if variant == "no-code":
                code = "0x"
            codes = {POOL: code, "0x" + "00" * 20: code}
            add(
                f"reference-{kind}-{variant}",
                0x3F5C,
                [128, int(p.ARGS[4][0], 16)],
                mw(m),
                "referencePrice",
                [p.META_TYPE, "address"],
                [m, p.ARGS[4][0]],
                2,
                code=codes,
            )
    # Inverse division precedes normalization. Nonintegral ratios and decimal
    # boundaries distinguish this from squaring the base-token decimal scale.
    for dec in [0, 6, 8, 18, 36, 39, 71, 72]:
        for sqrt in [2**96 + 12345678901234567890123, 2**97 + 19, 2**128 - 1]:
            m = copy.deepcopy(M)
            m[1], m[3], m[4], m[11], m[12] = dec, 3, 3, POOL, 2
            code = responder({"3850c7bd": encode(["uint256"], [sqrt])})
            add(
                f"reference-inverse-rounding-{dec}-{sqrt}",
                0x3F5C,
                [128, int(p.ARGS[4][0], 16)],
                mw(m),
                "referencePrice",
                [p.META_TYPE, "address"],
                [m, p.ARGS[4][0]],
                2,
                code={POOL: code},
            )
    return out
