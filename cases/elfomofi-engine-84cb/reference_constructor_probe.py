import copy, json
from eth_abi import encode
import constructor_probe as p

CANDIDATE = bytes.fromhex(
    json.loads((p.BUILD / "state-compiled.json").read_text())["evm"]["bytecode"][
        "object"
    ]
)
POOL = "0x" + "44" * 20
MANAGER = "0x" + "33" * 20


def responder(responses):
    code = bytearray.fromhex("5f3560e01c")
    patches = []
    for selector, result in responses.items():
        code += bytes.fromhex("8063" + selector + "1461")
        patches.append((len(code), result))
        code += bytes(2) + b"\x57"
    code += bytes.fromhex("5f5ffd")
    for at, result in patches:
        code[at : at + 2] = len(code).to_bytes(2, "big")
        code += bytes.fromhex("5b50")
        for offset in range(0, len(result), 32):
            code += (
                b"\x7f"
                + result[offset : offset + 32].ljust(32, b"\0")
                + b"\x60"
                + bytes([offset])
                + b"\x52"
            )
        code += b"\x60" + bytes([len(result)]) + bytes.fromhex("5ff3")
    return "0x" + code.hex()


def scenarios():
    base, quote = p.ARGS[4][0], p.ARGS[2]
    out = []
    for kind in range(6):
        for scenario in [
            "normal",
            "zero-ref",
            "zero-aux",
            "zero-manager",
            "wrong-token0",
            "wrong-token1",
            "reverse-pair",
            "zero-v3-price",
            "dirty-v3-price",
            "zero-v4-price",
            "dirty-v4-price",
            "short-v3",
            "short-v4",
            "no-pool-code",
            "no-manager-code",
        ]:
            args = copy.deepcopy(p.ARGS)
            m = args[5][0]
            m[3] = kind
            m[4] = 1
            m[6] = 1
            m[11] = MANAGER if kind == 4 else POOL
            m[12] = 1
            args[3] = MANAGER
            t0, t1 = base, quote
            sqrt3, sqrt4 = 1, 1
            if scenario == "zero-ref":
                m[11] = "0x" + "00" * 20
            if scenario == "zero-aux":
                m[12] = 0
            if scenario == "zero-manager":
                args[3] = "0x" + "00" * 20
            if scenario == "wrong-token0":
                t0 = POOL
            if scenario == "wrong-token1":
                t1 = POOL
            if scenario == "reverse-pair":
                t0, t1 = t1, t0
            if scenario == "zero-v3-price":
                sqrt3 = 0
            if scenario == "dirty-v3-price":
                sqrt3 = 1 << 160
            if scenario == "zero-v4-price":
                sqrt4 = 0
            if scenario == "dirty-v4-price":
                sqrt4 = 1 << 160
            code = {
                POOL: responder(
                    {
                        "0dfe1681": encode(["address"], [t0]),
                        "d21220a7": encode(["address"], [t1]),
                        "3850c7bd": b"\x01"
                        if scenario == "short-v3"
                        else encode(["uint256"], [sqrt3]),
                    }
                ),
                MANAGER: responder(
                    {
                        "1e2eaeaf": b"\x01"
                        if scenario == "short-v4"
                        else encode(["uint256"], [sqrt4])
                    }
                ),
            }
            if scenario == "no-pool-code":
                code[POOL] = "0x"
            if scenario == "no-manager-code":
                code[MANAGER] = "0x"
            out.append((f"kind-{kind}-{scenario}", args, code))
    return out
