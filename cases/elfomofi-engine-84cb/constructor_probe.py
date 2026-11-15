"""Offline constructor experiments. Fresh parent/child storage starts at zero.

Other uncaptured dependencies fail closed; no RPC or broadcasting is available.
"""

import copy
import json
import sys
from pathlib import Path
from eth_abi import decode, encode
from eth_utils import keccak

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "cases/elfomofi-pricing"))
from engine_lab import make_state, invoke, addr

P = Path(__file__).resolve().parent
CASE = P
BUILD = REPO / "build/elfomofi-engine-checkpoint"
ENGINE = "0x84cb1a96e57e9b88cf75035384c06dc3769654ae"
HELPER = "0x42e88fbc20c66bfe4bac17892980b640990d8cbc"
META_TYPE = "(uint8,uint8,uint8,uint8,uint8,uint16,uint8,uint128,uint16,uint16,uint8,address,uint256)"
TYPES = ["address"] * 4 + ["address[]", META_TYPE + "[]"] + ["uint8"] * 3
ARG_BYTES = bytes.fromhex(
    (CASE / "constructor-arguments.hex").read_text().strip().removeprefix("0x")
)
ARGS = list(decode(TYPES, ARG_BYTES))
ARGS[4] = list(ARGS[4])
ARGS[5] = [list(x) for x in ARGS[5]]
ORIGINAL = bytes.fromhex(
    (CASE / "chain-creation-input.hex").read_text().strip().removeprefix("0x")
)[: -len(ARG_BYTES)]
HEADER = json.loads((CASE / "evidence/block.json").read_text())
DEPLOYER = json.loads((CASE / "evidence/deployment.json").read_text())["transaction"][
    "from"
]
WITNESS = json.loads((CASE / "evidence/constructor-witness.json").read_text())
NATIVE = json.loads((CASE / "evidence/native-decimals.json").read_text())


def native_decimals(c):
    if not (
        c.msg.is_static
        and c.msg.value == 0
        and c.msg.sender == addr(ENGINE)
        and c.msg.data_as_bytes == bytes.fromhex("313ce567")
    ):
        raise ValueError("Uncaptured native call")
    c.output = bytes.fromhex(NATIVE["result"][2:])
    return c


def run(args, creation=ORIGINAL, extra_code=None):
    witness = copy.deepcopy(WITNESS)
    witness[ENGINE] = {
        "code": "0x" + (creation + encode(TYPES, args)).hex(),
        "storage": {},
    }
    witness[HELPER] = {"code": "0x", "storage": {}}
    fetched = []

    def fetch(method, params):
        if method == "eth_getStorageAt" and params[0] in (ENGINE, HELPER):
            return "0x" + "00" * 32
        raise ValueError(f"Uncaptured constructor dependency: {method} {params}")

    vm = make_state(
        witness,
        HEADER,
        fetch=fetch,
        code_overrides=extra_code or {},
        precompiles={addr(NATIVE["call"]["to"]): native_decimals},
    )
    vm.state.set_nonce(addr(ENGINE), 1)
    c = invoke(vm, b"", to=ENGINE, sender=DEPLOYER, origin=DEPLOYER)

    def call_tree(x):
        return {
            "to": "0x" + x.msg.to.hex(),
            "data": "0x" + x.msg.data_as_bytes.hex(),
            "error": x.is_error,
            "output": ("0x" + x.output.hex()) if x.msg.to else None,
            "children": [call_tree(y) for y in x.children],
        }

    error = None
    if c.is_error:
        if c.output[:4] == bytes.fromhex("08c379a0"):
            error = decode(["string"], c.output[4:])[0]
        elif c.output[:4] == bytes.fromhex("4e487b71"):
            error = "panic:" + hex(int.from_bytes(c.output[4:], "big"))
        else:
            error = "0x" + c.output.hex()
    storage = (
        {
            k: hex(vm.state.get_storage(addr(ENGINE), int(k, 16)))
            for k in sorted(witness[ENGINE]["storage"])
        }
        if not c.is_error
        else {}
    )
    result = {
        "success": not c.is_error,
        "error": error,
        "storage": storage,
        "calls": [call_tree(x) for x in c.children],
    }
    return result, vm, witness, fetched, c


def scenarios():
    out = [("baseline", copy.deepcopy(ARGS))]

    def add(name, mutate):
        a = copy.deepcopy(ARGS)
        mutate(a)
        out.append((name, a))

    zero = "0x" + "00" * 20
    for i in range(4):
        add(f"zero-address-{i}", lambda a, i=i: a.__setitem__(i, zero))
    for i in [6, 7, 8]:
        for v in [0, 1, 4, 5, 6, 10, 11, 15, 16, 251, 252, 255]:
            add(f"arg-{i}-{v}", lambda a, i=i, v=v: a.__setitem__(i, v))
    for field, values in [
        (0, [0, 1, 2, 3, 7, 8, 255]),
        (1, [0, 6, 8, 12, 18, 255]),
        (2, [0, 12, 13]),
        (3, [0, 1, 2, 3, 4, 5, 6, 255]),
        (4, [0, 1, 255]),
        (5, [0, 1, 65535]),
        (6, [0, 1, 255]),
        (7, [0, 1, 2**128 - 1]),
        (8, [0, 1, 9, 10, 150, 65535]),
        (9, [0, 149, 150, 151, 65535]),
        (10, [0, 1, 255]),
        (11, [zero]),
        (12, [0, 1, 2**256 - 1]),
    ]:
        for value in values:
            add(
                f"metadata-0-field-{field}-{value}",
                lambda a, f=field, v=value: a[5][0].__setitem__(f, v),
            )
    add("empty-tokens", lambda a: a.__setitem__(4, []))
    add("empty-metadata", lambda a: a.__setitem__(5, []))
    add("nine-tokens", lambda a: a.__setitem__(4, a[4] * 3))
    add("duplicate-token", lambda a: a[4].__setitem__(1, a[4][0]))
    add("token-is-quote", lambda a: a[4].__setitem__(0, a[2]))
    add("token-zero", lambda a: a[4].__setitem__(0, zero))
    add("reverse-indices", lambda a: [a[5][i].__setitem__(0, 2 - i) for i in range(3)])
    return out
