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
