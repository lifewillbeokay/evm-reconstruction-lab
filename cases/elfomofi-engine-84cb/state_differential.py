import copy
import json
import random
from eth_abi import encode
from eth_utils import keccak
import constructor_probe as p
from engine_lab import invoke, addr

CANDIDATE = bytes.fromhex(
    json.loads((p.BUILD / "state-compiled.json").read_text())["evm"]["bytecode"][
        "object"
    ]
)
OPERATORS = json.loads(
    (p.REPO / "cases/elfomofi-pricing/evidence/operator-addresses.json").read_text()
)
OUTSIDER = "0x" + "11" * 20
PROXY = p.ARGS[0]
COW = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"


def fixture(name, data, sender=p.DEPLOYER, extra_code=None, value=0):
    return dict(
        name=name, data=data, sender=sender, extra_code=extra_code or {}, value=value
    )


def scenarios():
    out = []

    def call(name, selector, types, values, **kwargs):
        out.append(
            fixture(name, bytes.fromhex(selector) + encode(types, values), **kwargs)
        )

    for token in p.ARGS[4] + ["0x" + "00" * 20, OUTSIDER]:
        call("metadata-" + token, "2a50c146", ["address"], [token])
        call("counters-" + token, "ac7ce2d5", ["address"], [token])
    call("pairs", "d527c998", [], [])
    for code in ["0x", "0x00", "0x60005f5260205ff3"]:
        call("codesize-" + code, "ef5c4d1c", [], [], extra_code={COW: code})
    timestamp = int(p.HEADER["timestamp"], 16)
    for i, word in enumerate(
        [
            0,
            timestamp - 1,
            timestamp,
            timestamp + 1,
            2**32 - 1,
            2**32,
            2**256 - 1,
            (1234567 << 32) + timestamp,
        ]
    ):
        call(f"prices-{i}", "ae7e8d81", ["uint256"], [word])
    for sender in OPERATORS + [OUTSIDER]:
        call(
            "price-auth-" + sender,
            "ae7e8d81",
            ["uint256"],
            [123456 << 32],
            sender=sender,
        )
    for size in [0, 1, 4, 14, 15, 16, 31, 32, 33, 100]:
        out.append(fixture("fallback-length-" + str(size), b"\xff" * size))
    for i, word in enumerate(
        [0, timestamp, timestamp + 1, (1234567 << 32) + timestamp, (1 << 120) - 1]
    ):
        out.append(fixture("fallback-word-" + str(i), word.to_bytes(15, "big")))
    for sender in OPERATORS + [OUTSIDER]:
        out.append(fixture("fallback-auth-" + sender, b"\xfe" * 15, sender=sender))
    configs = [
        ([], []),
        ([0], [0]),
        ([0], [257]),
        ([0], [1]),
        ([0], [8]),
        ([0], [1 << 232]),
        ([0], [257 | (1 << 232)]),
        ([0], [1 << 255]),
        ([3], [0]),
        ([2**256 - 1], [0]),
        ([0, 1], [0]),
        ([0, 1, 2], [0, 257, 514]),
        ([0, 0], [0, 257]),
    ]
    for i, args in enumerate(configs):
        call("config-" + str(i), "d4ff31bd", ["uint256[]", "uint256[]"], args)
    for n in range(8):
        word = n
        for j in range(n):
            word |= ((j + 1) | ((j * 100) << 16)) << (8 + j * 32)
        call(f"config-count-{n}", "d4ff31bd", ["uint256[]", "uint256[]"], [[0], [word]])
        if n:
            call(
                f"config-zero-last-{n}",
                "d4ff31bd",
                ["uint256[]", "uint256[]"],
                [[0], [word & ~(65535 << (8 + (n - 1) * 32))]],
            )
        call(
            f"config-high-bit-{n}",
            "d4ff31bd",
            ["uint256[]", "uint256[]"],
            [[0], [word | (1 << (8 + n * 32))]],
        )
    for sender in OPERATORS + [OUTSIDER]:
        call(
            "config-auth-" + sender,
            "d4ff31bd",
            ["uint256[]", "uint256[]"],
            [[0], [257]],
            sender=sender,
        )
    for selector in ["0323d901", "cebfd44d"]:
        for length in [0, 1, 19, 20, 21, 22, 31, 32, 100]:
            call(
                f"forward-{selector}-length-{length}",
                selector,
                ["bytes"],
                [b"\xaa" * length],
                extra_code={PROXY: "0x00"},
            )
        for proxycode in [
            "0x",
            "0x00",
            "0x63deadbeef5f5260205ff3",
            "0x63deadbeef5f5260205ffd",
        ]:
            call(
                f"forward-{selector}-proxy-{proxycode}",
                selector,
                ["bytes"],
                [bytes.fromhex(p.ARGS[4][0][2:]) + b"\x13"],
                extra_code={PROXY: proxycode},
            )
        for sender in OPERATORS + [OUTSIDER]:
            call(
                f"forward-auth-{selector}-{sender}",
                selector,
                ["bytes"],
                [b"\xaa" * 21],
                sender=sender,
                extra_code={PROXY: "0x00"},
            )
    # Deterministic arbitrary ladder words exercise count, trailing-bit and size
    # validation without assuming which invalid condition takes precedence.
    random.seed(8453)
    for i in range(30):
        call(
            "config-random-" + str(i),
            "d4ff31bd",
            ["uint256[]", "uint256[]"],
            [[random.randrange(5)], [random.getrandbits(256)]],
        )
    return out


def run(creation, case):
    _, vm, witness, _, c = p.run(
        p.ARGS, creation=creation, extra_code=case["extra_code"]
    )
    assert not c.is_error
    vm.state.set_code(addr(p.ENGINE), c.output)
    c = invoke(
        vm, case["data"], to=p.ENGINE, sender=case["sender"], origin=case["sender"]
    )

    def tree(x):
        return {
            "to": x.msg.to.hex(),
            "data": x.msg.data_as_bytes.hex(),
            "error": x.is_error,
            "output": x.output.hex(),
            "children": [tree(y) for y in x.children],
        }

    slots = {
        k: hex(vm.state.get_storage(addr(p.ENGINE), int(k, 16)))
        for k in sorted(witness[p.ENGINE]["storage"])
    }
    return {
        "error": c.is_error,
        "output": c.output.hex(),
        "storage": {k: v for k, v in slots.items() if int(v, 16)},
        "calls": [tree(x) for x in c.children],
        "logs": [(a.hex(), list(t), d.hex()) for a, t, d in c.get_log_entries()],
    }
