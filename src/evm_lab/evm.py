"""Local EVM message execution with caller-supplied state; never broadcasts."""
from dataclasses import dataclass
from eth.chains.base import MiningChain
from eth.db.atomic import AtomicDB
from eth.vm.forks.paris import ParisVM
from eth.vm.forks.shanghai import ShanghaiVM
from eth.vm.forks.cancun import CancunVM
from eth.vm.message import Message
from eth_utils import keccak

FORKS = {"paris": ParisVM, "shanghai": ShanghaiVM, "cancun": CancunVM}


@dataclass(frozen=True)
class Context:
    address: bytes
    sender: bytes
    timestamp: int = 1701337067
    chain_id: int = 1
    fork: str = "shanghai"
    coinbase: bytes = bytes(20)
    gas: int = 30_000_000


def make_vm(context: Context):
    if context.fork not in FORKS:
        raise ValueError(f"Supported forks: {', '.join(FORKS)}")
    if any(len(a) != 20 for a in (context.address, context.sender, context.coinbase)):
        raise ValueError("EVM addresses must be 20 bytes")
    chain_type = MiningChain.configure(__name__="SandboxChain",
        vm_configuration=((0, FORKS[context.fork]),), chain_id=context.chain_id)
    chain = chain_type.from_genesis(AtomicDB(), {
        "difficulty": 0, "gas_limit": context.gas, "timestamp": context.timestamp,
        "coinbase": context.coinbase,
    }, {})
    return chain.get_vm(chain.header.copy(timestamp=context.timestamp, coinbase=context.coinbase))


def execute(vm, context: Context, code: bytes, data=b"", value=0):
    """Apply a message, including value transfer and rollback on revert.

    Does not model signed transactions, nonce validation, intrinsic gas, or fees.
    Callers must seed account balances/storage/code explicitly.
    """
    message = Message(gas=context.gas, to=context.address, sender=context.sender,
                      value=value, data=data, code=code)
    tx = vm.state.get_transaction_context_class()(gas_price=1, origin=context.sender)
    return vm.state.computation_class.apply_message(vm.state, message, tx)


def constructor_runtime(initcode: bytes, context: Context) -> bytes:
    """Run zero-value initcode in empty synthetic state at the intended address.

    This is not a full CREATE transaction or historical replay. For constructors
    depending on external state, provide your own initialized VM and execution.
    """
    vm = make_vm(context)
    computation = execute(vm, context, initcode)
    if computation.is_error:
        raise ValueError(f"Constructor execution failed: {computation.error!r}")
    return computation.output


def mapping_slot(key: bytes | int, slot: int) -> int:
    if isinstance(key, bytes):
        key = int.from_bytes(key, "big")
    return int.from_bytes(keccak(key.to_bytes(32, "big") + slot.to_bytes(32, "big")), "big")


def capture(vm, computation, storage_keys=(), balance_addresses=()) -> dict:
    """Compare observable behavior, not gas; watch storage locations explicitly."""
    def calls(c):
        return [{"to": x.msg.to.hex(), "data": x.msg.data_as_bytes.hex(),
                 "value": x.msg.value, "error": x.is_error, "output": x.output.hex(),
                 "children": calls(x)} for x in c.children]
    return {"error": computation.is_error, "output": computation.output.hex(),
            "calls": calls(computation),
            "logs": [(a.hex(), list(t), d.hex()) for a, t, d in computation.get_log_entries()],
            "storage": {a.hex() + ":" + str(k): vm.state.get_storage(a, k) for a, k in storage_keys},
            "balances": {a.hex(): vm.state.get_balance(a) for a in balance_addresses}}
