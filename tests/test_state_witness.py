"""Regressions for the state-witness harness introduced by the ElfomoFi case."""

import importlib.util
import json
from pathlib import Path

import pytest

CASE = Path(__file__).resolve().parents[1] / "cases/elfomofi-pricing"
spec = importlib.util.spec_from_file_location(
    "elfomo_engine_lab", CASE / "engine_lab.py"
)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
A = "0x" + "11" * 20


def witness_for(code, storage):
    # Cancun VM initialization reads the beacon-root system contract.
    captured = json.loads((CASE / "evidence/state-witness.json").read_text())
    beacon = "0x000f3df6d732807ef1319fb7b8bb8522d0beac02"
    return {beacon: captured[beacon], A: {"code": code, "storage": storage}}


def test_captured_state_survives_reverted_message():
    header = json.loads((CASE / "evidence/block.json").read_text())
    # Read slot 0, replace it, then revert. The captured value must survive.
    witness = witness_for("0x6000545060026000555f5ffd", {"0x0": "0x1"})
    vm = lab.make_state(witness, header)
    assert lab.invoke(vm, b"", to=A).is_error
    assert vm.state.get_storage(lab.addr(A), 0) == 1


def test_uncaptured_storage_is_not_silently_zero():
    header = json.loads((CASE / "evidence/block.json").read_text())
    vm = lab.make_state(witness_for("0x60015400", {}), header)
    for _ in range(2):
        with pytest.raises(ValueError, match="Uncaptured slot"):
            lab.invoke(vm, b"", to=A)


def test_explicit_native_fixture_preserves_marker_and_rejects_unknown_calls():
    header = json.loads((CASE / "evidence/block.json").read_text())
    native = bytes.fromhex("b200" + "00" * 18)
    selector = bytes.fromhex("313ce567")
    # Store decimals() calldata, STATICCALL the native address, return its word.
    code = bytes.fromhex("63313ce56760e01b5f5260205f60045f73") + native
    code += bytes.fromhex("5afa5060205ff3")
    witness = witness_for("0x" + code.hex(), {})
    witness["0x" + native.hex()] = {"code": "0xef", "storage": {}}

    def decimals(c):
        if not (c.msg.is_static and c.msg.sender == lab.addr(A)
                and c.msg.data_as_bytes == selector):
            raise ValueError("Uncaptured native call")
        c.output = (8).to_bytes(32, "big")
        return c

    vm = lab.make_state(witness, header, precompiles={native: decimals})
    c = lab.invoke(vm, b"", to=A)
    assert not c.is_error and int.from_bytes(c.output, "big") == 8
    assert vm.state.get_code(native) == b"\xef"
    with pytest.raises(ValueError, match="Uncaptured native call"):
        lab.invoke(vm, b"", to="0x" + native.hex())
