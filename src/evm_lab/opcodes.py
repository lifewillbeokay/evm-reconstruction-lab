"""Instruction-aware inspection; PUSH4 constants are candidates, not ABI proof."""
from .bytecode import split_metadata, jsonable

_NAMES = {
    0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV",
    0x05: "SDIV", 0x06: "MOD", 0x07: "SMOD", 0x08: "ADDMOD", 0x09: "MULMOD",
    0x0a: "EXP", 0x0b: "SIGNEXTEND", 0x10: "LT", 0x11: "GT", 0x12: "SLT",
    0x13: "SGT", 0x14: "EQ", 0x15: "ISZERO", 0x16: "AND", 0x17: "OR",
    0x18: "XOR", 0x19: "NOT", 0x1a: "BYTE", 0x1b: "SHL", 0x1c: "SHR",
    0x1d: "SAR", 0x20: "KECCAK256", 0x30: "ADDRESS", 0x31: "BALANCE",
    0x32: "ORIGIN", 0x33: "CALLER", 0x34: "CALLVALUE", 0x35: "CALLDATALOAD",
    0x36: "CALLDATASIZE", 0x37: "CALLDATACOPY", 0x38: "CODESIZE",
    0x39: "CODECOPY", 0x3a: "GASPRICE", 0x3b: "EXTCODESIZE",
    0x3c: "EXTCODECOPY", 0x3d: "RETURNDATASIZE", 0x3e: "RETURNDATACOPY",
    0x3f: "EXTCODEHASH", 0x40: "BLOCKHASH", 0x41: "COINBASE", 0x42: "TIMESTAMP",
    0x43: "NUMBER", 0x44: "PREVRANDAO", 0x45: "GASLIMIT", 0x46: "CHAINID",
    0x47: "SELFBALANCE", 0x48: "BASEFEE", 0x49: "BLOBHASH", 0x4a: "BLOBBASEFEE",
    0x50: "POP", 0x51: "MLOAD", 0x52: "MSTORE", 0x53: "MSTORE8", 0x54: "SLOAD",
    0x55: "SSTORE", 0x56: "JUMP", 0x57: "JUMPI", 0x58: "PC", 0x59: "MSIZE",
    0x5a: "GAS", 0x5b: "JUMPDEST", 0x5c: "TLOAD", 0x5d: "TSTORE",
    0x5e: "MCOPY", 0x5f: "PUSH0", 0xf0: "CREATE", 0xf1: "CALL",
    0xf2: "CALLCODE", 0xf3: "RETURN", 0xf4: "DELEGATECALL", 0xf5: "CREATE2",
    0xfa: "STATICCALL", 0xfd: "REVERT", 0xfe: "INVALID", 0xff: "SELFDESTRUCT",
}


def disassemble(code: bytes):
    pc = 0
    while pc < len(code):
        op = code[pc]
        width = op - 0x5f if 0x60 <= op <= 0x7f else 0
        if width:
            name = f"PUSH{width}"
        elif 0x80 <= op <= 0x8f:
            name = f"DUP{op - 0x7f}"
        elif 0x90 <= op <= 0x9f:
            name = f"SWAP{op - 0x8f}"
        elif 0xa0 <= op <= 0xa4:
            name = f"LOG{op - 0xa0}"
        else:
            name = _NAMES.get(op, f"UNKNOWN_0x{op:02x}")
        immediate = code[pc + 1:pc + 1 + width]
        yield {"pc": pc, "opcode": f"0x{op:02x}", "name": name,
               "operand": immediate.hex(), "truncated": len(immediate) != width}
        pc += 1 + width


def inspect(code: bytes) -> dict:
    parts = split_metadata(code)
    instructions = list(disassemble(parts.executable))
    return {"bytes": len(code), "metadata": jsonable(parts.decoded),
            "metadata_bytes": len(parts.metadata),
            "push4_candidates": [dict(pc=x["pc"], value="0x" + x["operand"])
                                 for x in instructions if x["name"] == "PUSH4" and not x["truncated"]],
            "warning": "Linear disassembly includes embedded data. PUSH4 constants may be external-call selectors, errors, or ordinary data; this is not a recovered ABI."}
