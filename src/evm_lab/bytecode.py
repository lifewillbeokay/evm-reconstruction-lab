"""Strict bytecode loading and conservative terminal metadata detection."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

import cbor2
from eth_utils import keccak


def parse_hex(value: str) -> bytes:
    value = value.strip().removeprefix("0x")
    if len(value) % 2 or not re.fullmatch(r"[0-9a-fA-F]*", value):
        raise ValueError("Expected even-length hex bytes (optional 0x prefix)")
    return bytes.fromhex(value)


def read_hex(path: str | Path) -> bytes:
    return parse_hex(Path(path).read_text())


@dataclass(frozen=True)
class BytecodeParts:
    executable: bytes
    metadata: bytes
    decoded: dict | None


def split_metadata(code: bytes) -> BytecodeParts:
    """Recognize a complete terminal CBOR map with compiler/source-hash keys.

    This is structural recognition, not proof that the suffix is unreachable.
    Unknown, malformed, or ambiguous suffixes are retained in executable bytes.
    """
    untouched = BytecodeParts(code, b"", None)
    if len(code) < 3:
        return untouched
    length = int.from_bytes(code[-2:], "big")
    if length == 0 or length + 2 >= len(code):
        return untouched
    payload = code[-length - 2:-2]
    stream = BytesIO(payload)
    try:
        data = cbor2.CBORDecoder(stream).decode()
    except (ValueError, TypeError, EOFError, RecursionError, cbor2.CBORDecodeError):
        return untouched
    if stream.tell() != length or not isinstance(data, dict):
        return untouched
    if not any(key in data for key in ("solc", "vyper", "ipfs", "bzzr0", "bzzr1")):
        return untouched
    return BytecodeParts(code[:-length - 2], code[-length - 2:], data)


def jsonable(value):
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def first_difference(a: bytes, b: bytes) -> int | None:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b)) if len(a) != len(b) else None


def compare(a: bytes, b: bytes) -> dict:
    ap, bp = split_metadata(a), split_metadata(b)
    offset = first_difference(ap.executable, bp.executable)
    start = max(0, (offset or 0) - 16)
    return {
        "exact_match": a == b,
        "executable_match": ap.executable == bp.executable,
        "metadata_match": ap.metadata == bp.metadata,
        "original_has_recognized_metadata": ap.decoded is not None,
        "candidate_has_recognized_metadata": bp.decoded is not None,
        "original_bytes": len(a), "candidate_bytes": len(b),
        "original_keccak256": "0x" + keccak(a).hex(),
        "candidate_keccak256": "0x" + keccak(b).hex(),
        "first_executable_difference": offset,
        "difference_context": None if offset is None else {
            "start": start,
            "original": ap.executable[start:offset + 17].hex(),
            "candidate": bp.executable[start:offset + 17].hex(),
        },
    }
