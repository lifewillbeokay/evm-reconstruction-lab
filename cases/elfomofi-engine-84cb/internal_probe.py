"""Synthetic internal-entry and jump-destination experiments on captured code.

This is deliberately not a transaction replay: entry stack/memory can be seeded.
No target bytecode is patched. Optional GAS substitution and chain/storage
overrides are explicitly synthetic. Halt at a selected return PC in the tracer.
"""

import copy
import json
import constructor_probe as p
from eth.exceptions import Halt
from engine_lab import make_state, invoke, addr


def probe(
    entry=None,
    stack=(),
    words=None,
    data=b"",
    overrides=None,
    code=None,
    stop=0xE,
    trace=True,
    sender=None,
    origin=None,
    timestamp=None,
    transient=None,
    chain_id=None,
    gas_value=None,
    synthetic_storage=None,
):
    witness = copy.deepcopy(
        json.loads((p.CASE / "evidence/state-witness-getters.json").read_text())
    )
    # Explicit synthetic state is distinct from captured evidence. Unlisted
    # dependencies still fail closed in make_state.
    for account, slots in (synthetic_storage or {}).items():
        witness.setdefault(account, {"storage": {}})["storage"].update(slots)
    vm = make_state(
        witness,
        p.HEADER,
        storage_overrides=overrides,
        code_overrides=code,
        timestamp=timestamp,
    )
    if chain_id is not None:
        vm.state.execution_context._chain_id = chain_id
    base = vm.state.computation_class
    records = []
    original = base.opcodes[0x5B]
    original_gas = base.opcodes[0x5A]

    def gas(computation):
        original_gas(computation=computation)
        if gas_value is not None and computation.msg.code_address == addr(p.ENGINE):
            computation.stack_pop1_int()
            computation.stack_push_int(gas_value)

    def jumpdest(computation):
        pc = computation.code.program_counter - 1
        if computation.msg.code_address == addr(p.ENGINE):
            if trace:
                records.append(
                    {
                        "pc": hex(pc),
                        "stack": [
                            hex(x if isinstance(x, int) else int.from_bytes(x, "big"))
                            for x in computation._stack.values
                        ],
                        "memory": computation._memory.read_bytes(
                            0, len(computation._memory)
                        ).hex(),
                    }
                )
            if entry is not None and pc == stop:
                raise Halt("synthetic internal return")
        return original(computation=computation)

    class Instrumented(base):
        opcodes = {**base.opcodes, 0x5B: jumpdest, 0x5A: gas}

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.msg.code_address == addr(p.ENGINE):
                for slot, value in (transient or {}).items():
                    self.state.set_transient_storage(
                        addr(p.ENGINE), slot, (value % (1 << 256)).to_bytes(32, "big")
                    )
            if entry is not None and self.msg.code_address == addr(p.ENGINE):
                self.code.program_counter = entry
                for v in stack:
                    self.stack_push_int(v % (1 << 256))
                initial = {0x40: 0x1000, **(words or {})}
                for at, value in initial.items():
                    self._memory.extend(at, 32)
                    self._memory.write(at, 32, (value % (1 << 256)).to_bytes(32, "big"))

    vm.state.computation_class = Instrumented
    c = invoke(
        vm, data, to=p.ENGINE, sender=sender or p.ARGS[0], origin=origin or p.ARGS[0]
    )
    return c, records, vm
