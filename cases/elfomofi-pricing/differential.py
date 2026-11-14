"""Offline differential tests of the 15-selector dispatcher reconstruction.
External engines/classifier are explicit fixtures, not real liquidity simulations.
"""

import argparse, json
from pathlib import Path
from eth_abi import encode
from eth_utils import keccak
from eth.vm.message import Message
from evm_lab.bytecode import parse_hex
from evm_lab.evm import Context, make_vm, mapping_slot, capture

ROOT = Path(__file__).resolve().parent
ADDR = bytes.fromhex("ffffffbb2d432b8acb4c57d556c0c721a431d038")
SWAP = bytes.fromhex("f0f0f0f0fb0d738452efd03a28e8be14c76d5f73")
OWNER = bytes.fromhex("e4d317fc02dbc3bf88a7d5c0d5a527444bf322b0")
ADMIN = bytes.fromhex("423429453df78b5ed36ce1d6c1edcba41c3a358a")
ENGINE = bytes.fromhex("22" * 20)
CLASSIFIER = bytes.fromhex("33" * 20)
CALLER = bytes.fromhex("11" * 20)
A = bytes.fromhex("4200000000000000000000000000000000000006")
B = bytes.fromhex("833589fcd6edb6e08f4c7c32d4f71b54bda02913")
K = int("0146109eced2816f22a2937a116619ffffffffffff", 16)
ARRAY = int.from_bytes(keccak((102).to_bytes(32, "big")), "big")


def route_slot(a=A, b=B):
    return mapping_slot(int.from_bytes(a, "big") + int.from_bytes(b, "big") + K, 101)


def cd(sig, types=(), args=()):
    return bytes.fromhex(sig) + encode(types, args)


def reply(data=b"", revert=False):
    return (
        bytes.fromhex("61")
        + len(data).to_bytes(2, "big")
        + bytes.fromhex("61000f60003961")
        + len(data).to_bytes(2, "big")
        + bytes.fromhex("6000")
        + (b"\xfd" if revert else b"\xf3")
        + data
    )


def tests():
    cases = []

    def add(name, data, sender=CALLER, **kw):
        cases.append(dict(name=name, data=data, sender=sender, **kw))

    qtypes = ["address", "address", "uint256", "address", "uint256"]
    for sel in ["561fa97d", "6486c4ac"]:
        for amt in [0, 1, 10**18, 2**256 - 1]:
            for reverse in [False, True]:
                a, b = (B, A) if reverse else (A, B)
                data = cd(sel, qtypes, [a, b, amt, CALLER, 7])
                add(
                    f"{sel}-forward-{amt}-{reverse}",
                    data,
                    SWAP,
                    engine_output=encode(
                        ["uint256", "uint256", "bytes"], [123, 456, b"abcde"]
                    ),
                )
        add(sel + "-wrong-caller", cd(sel, qtypes, [A, B, 1, CALLER, 0]))
        add(
            sel + "-unconfigured",
            cd(sel, qtypes, [A, B, 1, CALLER, 0]),
            SWAP,
            no_engine=True,
        )
        add(
            sel + "-engine-revert",
            cd(sel, qtypes, [A, B, 1, CALLER, 0]),
            SWAP,
            engine_output=b"bad!",
            engine_revert=True,
        )
        add(
            sel + "-bad-return",
            cd(sel, qtypes, [A, B, 1, CALLER, 0]),
            SWAP,
            engine_output=b"",
        )
    add("owner", cd("8da5cb5b"))
    add("initialize", cd("c4d66de8", ["address"], [OWNER]), uninitialized=True)
    add(
        "initialize-zero-owner",
        cd("c4d66de8", ["address"], [bytes(20)]),
        uninitialized=True,
    )
    add("initialize-twice", cd("c4d66de8", ["address"], [OWNER]))
    for who in [OWNER, CALLER]:
        add("renounce-" + who.hex(), cd("715018a6"), who)
        for nxt in [CALLER, bytes(20)]:
            add(
                "transfer-" + who.hex() + nxt.hex(),
                cd("f2fde38b", ["address"], [nxt]),
                who,
            )
        add(
            "add-pair-" + who.hex(), cd("b6f3e087", ["address", "address"], [A, B]), who
        )
    for n in [0, 1, 3]:
        add("pairs-" + str(n), cd("d527c998"), SWAP, pair_count=n)
    add("pairs-access", cd("d527c998"))
    levels = encode(
        ["(uint256,uint256)[]", "(uint256,uint256)[]"], [[(2, 3), (4, 5)], [(6, 7)]]
    )
    add(
        "orderbook",
        cd("0a6e04cb", ["address", "address"], [A, B]),
        engine_output=levels,
    )
    add(
        "orderbook-missing",
        cd("0a6e04cb", ["address", "address"], [A, B]),
        no_engine=True,
    )
    add(
        "orderbook-revert",
        cd("0a6e04cb", ["address", "address"], [A, B]),
        engine_revert=True,
        engine_output=b"abcd",
    )
    for who in [OWNER, ADMIN, CALLER]:
        add("classifier-set-" + who.hex(), cd("19b4c955", ["address"], [ENGINE]), who)
    raw = (int.from_bytes(A, "big") + int.from_bytes(B, "big")).to_bytes(
        32, "big"
    ) + ENGINE
    for n in [0, 31, 32, 51, 52, 60]:
        add(
            "route-bytes-" + str(n),
            cd("2784993c", ["bytes"], [(raw + bytes(8))[:n]]),
            OWNER,
        )
    add("route-access", cd("2784993c", ["bytes"], [raw]))
    add(
        "route-overflow",
        cd("2784993c", ["bytes"], [bytes.fromhex("ff" * 32) + ENGINE]),
        OWNER,
    )
    for who in [ENGINE, CALLER]:
        for byte in [0, 1, 44, 255]:
            add(
                f"classifier-query-{who.hex()}-{byte}",
                cd(
                    "725e6ced",
                    ["address", "address", "address", "uint256"],
                    [A, B, CALLER, 9],
                ),
                who,
                classifier_output=encode(["uint8"], [byte]),
            )
    add(
        "classifier-missing",
        cd("725e6ced", ["address", "address", "address", "uint256"], [A, B, CALLER, 9]),
        ENGINE,
        no_classifier=True,
    )
    add(
        "classifier-invalid-uint8",
        cd("725e6ced", ["address", "address", "address", "uint256"], [A, B, CALLER, 9]),
        ENGINE,
        classifier_output=encode(["uint256"], [256]),
    )
    add(
        "classifier-revert",
        cd("725e6ced", ["address", "address", "address", "uint256"], [A, B, CALLER, 9]),
        ENGINE,
        classifier_revert=True,
        classifier_output=b"bad!",
    )
    for sel in ["fbecbad7", "d2ad58b5"]:
        for origin in [
            OWNER,
            CALLER,
            bytes.fromhex(
                json.loads((ROOT / "evidence/operator-addresses.json").read_text())[0][
                    2:
                ]
            ),
        ]:
            add(
                "operator-" + sel + origin.hex(),
                cd(sel, ["address", "uint8"], [CALLER, 7]),
                CALLER,
                origin=origin,
            )
    utypes = [
        "uint256",
        "bytes",
        "address",
        "address",
        "uint256",
        "uint256",
        "address",
        "uint256",
    ]
    for data in [b"", b"a", b"ab", b"abc", b"abcdef", bytes(65)]:
        add(
            "update-" + data.hex(),
            cd("519341bb", utypes, [77, data, A, B, 100, 200, CALLER, 9]),
            SWAP,
        )
    add(
        "update-no-engine",
        cd("519341bb", utypes, [77, b"abc", A, B, 100, 200, CALLER, 9]),
        SWAP,
        no_engine=True,
    )
    add(
        "update-no-classifier",
        cd("519341bb", utypes, [77, b"abc", A, B, 100, 200, CALLER, 9]),
        SWAP,
        no_classifier=True,
    )
    add(
        "update-unauthorized",
        cd("519341bb", utypes, [77, b"abc", A, B, 100, 200, CALLER, 9]),
    )
    for data in [b"", b"\x00", bytes.fromhex("deadbeef"), bytes.fromhex("561fa97d")]:
        add("malformed-" + data.hex(), data)
    return cases


def run(code, t):
    ctx = Context(ADDR, t["sender"], fork="cancun", chain_id=8453)
    vm = make_vm(ctx)
    base = {
        0: 0 if t.get("uninitialized") else 1,
        51: int.from_bytes(OWNER, "big"),
        103: 0 if t.get("no_classifier") else int.from_bytes(CLASSIFIER, "big"),
        102: t.get("pair_count", 1),
        route_slot(): 0 if t.get("no_engine") else int.from_bytes(ENGINE, "big"),
    }
    for i in range(t.get("pair_count", 1)):
        base[ARRAY + 2 * i] = int.from_bytes(A, "big")
        base[ARRAY + 2 * i + 1] = int.from_bytes(B, "big")
    for slot, value in base.items():
        vm.state.set_storage(ADDR, slot, value)
    vm.state.set_code(ADDR, code)
    vm.state.set_code(SWAP, reply())
    vm.state.set_code(
        ENGINE, reply(t.get("engine_output", b""), t.get("engine_revert", False))
    )
    vm.state.set_code(
        CLASSIFIER,
        reply(
            t.get("classifier_output", encode(["uint8"], [0])),
            t.get("classifier_revert", False),
        ),
    )
    msg = Message(
        gas=30000000, to=ADDR, sender=t["sender"], value=0, data=t["data"], code=code
    )
    tx = vm.state.get_transaction_context_class()(
        gas_price=1, origin=t.get("origin", t["sender"])
    )
    comp = vm.state.computation_class.apply_message(vm.state, msg, tx)
    watch = set(base) | {ARRAY, ARRAY + 1, ARRAY + 2, ARRAY + 3}
    return capture(vm, comp, [(ADDR, x) for x in sorted(watch)])


def main(candidate, output):
    original = parse_hex((ROOT / "chain-runtime.hex").read_text())
    candidate = parse_hex(candidate.read_text())
    results = []
    for t in tests():
        left = run(original, t)
        right = run(candidate, t)
        ok = left == right
        results.append(
            {"name": t["name"], "match": ok, "original_reverted": left["error"]}
        )
        if not ok:
            print(
                "FAIL",
                t["name"],
                json.dumps({"original": left, "candidate": right}, indent=2),
            )
    result = {
        "passed": sum(t["match"] for t in results),
        "total": len(results),
        "cases": results,
        "scope": "Synthetic dispatcher fixtures; compares returndata, reverts, calls, logs and watched storage. Not full system equivalence.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['passed']}/{result['total']} dispatcher differential cases")
    if result["passed"] != result["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    main(a.candidate, a.output)
