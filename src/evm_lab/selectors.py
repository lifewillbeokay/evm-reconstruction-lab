"""Keccak selectors, explicit signature decoding, and bounded collision search."""
import re
from eth_utils import keccak
from eth_abi import decode
from .bytecode import jsonable


def selector(signature: str) -> str:
    if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*\([^\s]*\)", signature):
        raise ValueError("Supply a canonical signature, e.g. transfer(address,uint256)")
    return "0x" + keccak(text=signature)[:4].hex()


def argument_types(signature: str) -> list[str]:
    selector(signature)
    args = signature[signature.index("(") + 1:-1]
    if not args:
        return []
    result, depth, start = [], 0, 0
    for i, c in enumerate(args):
        depth += (c == "(") - (c == ")")
        if depth < 0:
            raise ValueError("Unbalanced tuple in signature")
        if c == "," and depth == 0:
            result.append(args[start:i]); start = i + 1
    if depth:
        raise ValueError("Unbalanced tuple in signature")
    result.append(args[start:])
    return result


def decode_call(signature: str, calldata: bytes) -> dict:
    expected = selector(signature)
    if calldata[:4].hex() != expected[2:]:
        raise ValueError("Calldata selector does not match the supplied signature")
    return {"signature": signature, "selector": expected,
            "arguments": jsonable(decode(argument_types(signature), calldata[4:])),
            "note": "A matching selector does not prove this was the original function name."}


def mine_name(target: str, suffix: str, start: int, attempts: int, prefix="recovered_") -> dict:
    if not re.fullmatch(r"0x[0-9a-fA-F]{8}", target) or start < 0 or attempts < 1:
        raise ValueError("Target must be four bytes; start >= 0 and attempts >= 1")
    # Validate the proposed signature before entering a potentially expensive loop.
    argument_types(prefix + str(start) + suffix)
    for n in range(start, start + attempts):
        signature = prefix + str(n) + suffix
        if selector(signature) == target.lower():
            return {"found": True, "signature": signature, "selector": target.lower(),
                    "next_start": n + 1, "provenance": "synthetic_selector_collision"}
    return {"found": False, "next_start": start + attempts,
            "provenance": "synthetic_selector_collision"}
