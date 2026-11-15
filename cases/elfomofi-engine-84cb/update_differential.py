"""Controlled public update experiments against the captured runtime.

Synthetic balances/counters/transient words are explicit fixtures, not historical swaps.
"""

import itertools
import json
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
BLOCK = int(p.HEADER["number"], 16)
SIDE = "0x" + keccak(encode(["address", "uint256"], [T, 1])).hex()
STATS = [
    "0x"
    + keccak(
        encode(
            ["uint256", "bytes32"],
            [BLOCK, keccak(encode(["address", "uint256"], [T, i]))],
        )
    ).hex()
    for i in [3, 4]
]
META = int.from_bytes(keccak(encode(["address", "uint256"], [T, 5])), "big")
WITNESS = json.loads((p.CASE / "evidence/state-witness-getters.json").read_text())
KEYS = [
    int.from_bytes(keccak(bytes.fromhex(T[2:]) + bytes([i])), "big") for i in [0, 1]
] + [int("22116470a8a062b874d7fcbbce281f71f1c078a760833f3d2faa65621bd10bef", 16)]
EXEC = "0x1e90cb21b770d170821c0ebf56ce6ffd2942e5d4"
EXTRA_ORIGIN = "0x6e1d61f5bf0c9d4e3511c33ea93c04488206e179"


def scenarios():
    out = []

    def add(
        name,
        ask=False,
        amount=10**18,
        quote=10**6,
        marker=0,
        counter=1000,
        stats=0,
        opposite=0,
        kind=1,
        raw4=0,
        origin=None,
        executor=None,
        partner=0,
        sender=None,
        chain=8453,
        bounds=None,
        pair=None,
        payload=b"",
    ):
        a, b = pair or ((Q, T) if ask else (T, Q))
        fa, ta = (quote, amount) if ask else (amount, quote)
        word = int(WITNESS[p.ENGINE]["storage"][hex(META)], 16)
        word = (word & ~(65535 << 24)) | (kind << 24) | (raw4 << 32)
        slots = {
            SIDE: hex(counter + (counter << 16)),
            STATS[ask]: hex(stats),
            STATS[not ask]: hex(opposite),
        }
        calldata = bytes.fromhex("519341bb") + encode(
            [
                "uint256",
                "bytes",
                "address",
                "address",
                "uint256",
                "uint256",
                "address",
                "uint256",
            ],
            [marker << 208, payload, a, b, fa, ta, executor or p.ARGS[0], partner],
        )
        kwargs = {
            "synthetic_storage": {p.ENGINE: slots},
            "overrides": {p.ENGINE: {hex(META): hex(word)}},
            "origin": origin or p.ARGS[0],
            "sender": sender or p.ARGS[0],
            "chain_id": chain,
            "transient": bounds or {},
        }
        base = b if a == Q else a
        if base != T:
            location = int.from_bytes(
                keccak(encode(["address", "uint256"], [base, 5])), "big"
            )
            kwargs["synthetic_storage"][p.ENGINE].update(
                {hex(location + i): "0x0" for i in range(3)}
            )
        if chain == 4663:
            kwargs["code"] = {
                "0x" + "00" * 19 + "64": responder(
                    {"a3b1b31d": encode(["uint256"], [BLOCK])}
                )
            }
        out.append((name, calldata, kwargs))

    for ask, amount, kind, raw4 in itertools.product(
        [False, True],
        [0, 1, 12 * 10**17 - 1, 12 * 10**17, 48 * 10**17, 2**128 - 1, 2**128],
        [0, 1, 3, 4, 5, 6],
        [0, 1],
    ):
        add(
            f"amount-{ask}-{amount}-{kind}-{raw4}",
            ask=ask,
            amount=amount,
            kind=kind,
            raw4=raw4,
        )
    for ask, marker, to, counter in itertools.product(
        [False, True], [0, 1, 16, 17, 255], [1, 16, 17], [0, 15, 16, 1000]
    ):
        add(
            f"dust-{ask}-{marker}-{to}-{counter}",
            ask=ask,
            amount=to if ask else 10**18,
            quote=10**6 if ask else to,
            marker=marker,
            counter=counter,
        )
    for ask, field, count, opposite, divisor in itertools.product(
        [False, True],
        [0, 1, 2, 3],
        [0, 2, 3, 5, 6, 7, 8, 9, 10, 14, 15, 254, 255],
        [0, 6],
        [1, 2],
    ):
        shifts = [0, 128, 136, 144]
        stat = count << shifts[field]
        add(
            f"stats-{ask}-{field}-{count}-{opposite}-{divisor}",
            ask=ask,
            amount=5 * 10**18,
            stats=stat,
            opposite=opposite << 144,
            kind=3 if divisor == 2 else 1,
        )
    for ask, origin, executor, partner, sender in itertools.product(
        [False, True],
        [p.ARGS[0], p.DEPLOYER, EXTRA_ORIGIN],
        [p.ARGS[0], EXEC],
        [0, 0x120, 0x121, 0x194, 0x195, 2976, 2977],
        [p.ARGS[0], "0x" + "12" * 20],
    ):
        add(
            f"auth-{ask}-{origin}-{executor}-{partner}-{sender}",
            ask=ask,
            amount=5 * 10**18,
            origin=origin,
            executor=executor,
            partner=partner,
            sender=sender,
        )
    for ask, chain, slot, offset in itertools.product(
        [False, True], [56, 4663, 8453], range(3), [-1, 0, 1]
    ):
        value = 2 * 10**30 + offset
        add(
            f"transient-{ask}-{chain}-{slot}-{offset}",
            ask=ask,
            amount=100,
            quote=200,
            chain=chain,
            bounds={KEYS[slot]: value},
        )
    # The bytes argument is unused semantically but still ABI-decoded and copied.
    for ask, length in itertools.product(
        [False, True], [0, 1, 2, 31, 32, 33, 64, 4096]
    ):
        add(f"payload-{ask}-{length}", ask=ask, payload=b"\xa5" * length)
    zero = "0x" + "00" * 20
    unknown = "0x" + "12" * 20
    for a, b in [
        (T, T),
        (Q, Q),
        (zero, Q),
        (Q, zero),
        (unknown, Q),
        (Q, unknown),
        (T, unknown),
        (unknown, T),
        (zero, zero),
    ]:
        add(f"pair-{a}-{b}", pair=(a, b))
    # Inverting the observed uint160 transform creates fixtures, not identity labels.
    transformed = [
        0xA995EEE4E52E52927F39A6AA9AA25691F6DDAA56,
        0x5784974AE9AC7C1F56948528C08FA40DFC10BFBF,
        0x179FD775DDA7E5AB7F771289C4448380963D5979,
        0x7F05033B024C42EA9A7A57519251DE92FB5A2A1C,
    ]
    for value, ask, executor in itertools.product(
        transformed, [False, True], [p.ARGS[0], EXEC]
    ):
        origin = (
            "0x"
            + (
                (
                    (
                        (value ^ 0xC471DF69CD11FB228F690B7136037FFFFFFFFFFE)
                        - 0x7301C4CC2C1E69FFFE
                    )
                    * pow(0xD05, -1, 1 << 160)
                )
                % (1 << 160)
            )
            .to_bytes(20, "big")
            .hex()
        )
        add(
            f"special-origin-{origin}-{ask}-{executor}",
            ask=ask,
            origin=origin,
            executor=executor,
            amount=5 * 10**18,
        )
    add("abi-template")
    _, data, kwargs = out.pop()
    for offset in [0, 1, 31, 32, 255, 256, 257, 2**64, 2**256 - 1]:
        modified = data[:36] + offset.to_bytes(32, "big") + data[68:]
        out.append((f"abi-offset-{offset}", modified, kwargs))
    for length in [0, 31, 255, 256, 287, 288]:
        out.append((f"abi-truncated-{length}", data[: 4 + length], kwargs))
    for field in [2, 3, 6]:
        at = 4 + field * 32
        value = int.from_bytes(data[at : at + 32], "big") | (1 << 160)
        out.append(
            (
                f"abi-dirty-address-{field}",
                data[:at] + value.to_bytes(32, "big") + data[at + 32 :],
                kwargs,
            )
        )
    return out


def state(c, vm):
    def tree(x):
        return {
            "to": x.msg.to.hex(),
            "data": x.msg.data_as_bytes.hex(),
            "error": x.is_error,
            "output": x.output.hex(),
            "children": [tree(y) for y in x.children],
        }

    return {
        "error": c.is_error,
        "output": c.output.hex(),
        "calls": [tree(x) for x in c.children],
        "storage": [
            hex(vm.state.get_storage(bytes.fromhex(p.ENGINE[2:]), int(k, 16)))
            for k in [SIDE, *STATS]
        ],
        "transient": [
            vm.state.get_transient_storage(bytes.fromhex(p.ENGINE[2:]), k).hex()
            for k in KEYS
        ],
        "logs": [(a.hex(), list(t), d.hex()) for a, t, d in c.get_log_entries()],
    }


def run_all():
    rows = []
    for name, data, kwargs in scenarios():
        target, _, vm = probe(data=data, trace=False, **kwargs)
        t = state(target, vm)
        kw = dict(kwargs)
        kw["code"] = {**kw.get("code", {}), p.ENGINE: RUNTIME}
        candidate, _, vm = probe(data=data, trace=False, **kw)
        v = state(candidate, vm)
        rows.append({"name": name, "match": t == v, "target": t, "candidate": v})
    return rows


if __name__ == "__main__":
    rows = run_all()
    (p.BUILD / "update-differential.json").write_text(json.dumps(rows, indent=2) + "\n")
    summary = {
        "cases": len(rows),
        "matched": sum(x["match"] for x in rows),
        "failures": [x for x in rows if not x["match"]],
    }
    (p.BUILD / "update-differential-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps({**summary, "failures": summary["failures"][:5]}))
