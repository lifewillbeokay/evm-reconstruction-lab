"""Offline experiments against captured deployed engine bytes, with explicit state overrides.
A strict storage/code witness prevents silent zero-state assumptions. No broadcasting.
"""

import copy
from pathlib import Path
from eth_abi import encode, decode
from eth.chains.base import MiningChain
from eth.db.atomic import AtomicDB
from eth.vm.forks.cancun import CancunVM
from eth.vm.forks.cancun.state import CancunState
from eth.vm.message import Message

ROOT = Path(__file__).resolve().parent
PROXY = "0xffffffbb2d432b8acb4c57d556c0c721a431d038"
ENGINE = "0xd6ac027dbcbf19489e8ecd4d719aa83396eca3ee"
CLASSIFIER = "0x80d06229252825137f36e3484ea61c10b6235e29"
SWAP = "0xf0f0f0f0fb0d738452efd03a28e8be14c76d5f73"
WETH = "0x4200000000000000000000000000000000000006"
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
EXECUTOR = "0x1111111111111111111111111111111111111111"
META = int("113e300cbfcb107d961958639e10e4c56d214f1359f5d6fe43316ac71df69dbe", 16)


def addr(s):
    return bytes.fromhex(s.removeprefix("0x"))


def ret_word(x):
    return (
        bytes.fromhex("7f") + x.to_bytes(32, "big") + bytes.fromhex("60005260206000f3")
    )


def call_tree(c):
    return {
        "address": "0x" + c.msg.code_address.hex(),
        "data": "0x" + c.msg.data_as_bytes.hex(),
        "error": c.is_error,
        "output": "0x" + c.output.hex(),
        "calls": [call_tree(x) for x in c.children],
    }


def make_state(
    witness,
    header,
    storage_overrides=None,
    code_overrides=None,
    timestamp=None,
    fetch=None,
):
    loaded = set()
    codes = set()
    storage_overrides = storage_overrides or {}
    code_overrides = code_overrides or {}

    def account(a):
        return witness.setdefault("0x" + a.hex(), {"storage": {}})

    class State(CancunState):
        def get_code(self, address):
            a = "0x" + address.hex()
            d = account(address)
            if a not in codes:
                if a not in code_overrides and "code" not in d:
                    if fetch is None:
                        raise ValueError("Uncaptured code " + a)
                    d["code"] = fetch("eth_getCode", [a, header["number"]])
                self.set_code(address, addr(code_overrides.get(a, d.get("code", "0x"))))
                codes.add(a)
            return super().get_code(address)

        def get_storage(self, address, slot, from_journal=True):
            a = "0x" + address.hex()
            k = hex(slot)
            d = account(address)["storage"]
            if (a, k) not in loaded:
                if k not in d:
                    if fetch is None:
                        raise ValueError(f"Uncaptured slot {a} {k}")
                    d[k] = fetch("eth_getStorageAt", [a, k, header["number"]])
                self.set_storage(
                    address, slot, int(storage_overrides.get(a, {}).get(k, d[k]), 16)
                )
            return super().get_storage(address, slot, from_journal)

        def set_storage(self, address, slot, value):
            # A local write supersedes the captured value on subsequent reads.
            loaded.add(("0x" + address.hex(), hex(slot)))
            return super().set_storage(address, slot, value)

    class VM(CancunVM):
        _state_class = State

    ts = int(header["timestamp"], 16) if timestamp is None else timestamp
    chain = MiningChain.configure(
        __name__="ElfomoOfflineChain", vm_configuration=((0, VM),), chain_id=8453
    ).from_genesis(
        AtomicDB(), {"difficulty": 0, "gas_limit": 100000000, "timestamp": ts}, {}
    )
    vm = chain.get_vm(
        chain.header.copy(
            block_number=int(header["number"], 16),
            timestamp=ts,
            coinbase=addr(header["miner"]),
            base_fee_per_gas=int(header["baseFeePerGas"], 16),
        )
    )
    # Seed captured values outside any message journal: a later revert must not
    # roll back the initial witness while leaving the lazy-load cache populated.
    for address, record in list(witness.items()):
        if "code" in record or address in code_overrides:
            vm.state.get_code(addr(address))
        for slot in list(record["storage"]):
            vm.state.get_storage(addr(address), int(slot, 16))
    return vm


def invoke(vm, data, to=PROXY, sender=SWAP, origin=SWAP):
    a = addr(to)
    s = addr(sender)
    vm.state.clear_transient_storage()
    msg = Message(
        gas=30000000, to=a, sender=s, value=0, data=data, code=vm.state.get_code(a)
    )
    ctx = vm.state.get_transaction_context_class()(gas_price=1, origin=addr(origin))
    return vm.state.computation_class.apply_message(vm.state, msg, ctx)


def quote_data(
    amount=10**18, reverse=False, exact_out=False, executor=EXECUTOR, partner=0
):
    a, b = (USDC, WETH) if reverse else (WETH, USDC)
    return bytes.fromhex("6486c4ac" if exact_out else "561fa97d") + encode(
        ["address", "address", "uint256", "address", "uint256"],
        [a, b, amount, executor, partner],
    )


def scenarios():
    out = [{"name": "observed-zero-anchor", "price": None}]
    for p in [175000, 176000, 176200, 176245, 176300, 176500, 177000]:
        out.append({"name": f"anchor-{p}", "price": p})
    for amount in [
        10**14,
        10**16,
        10**17,
        5 * 10**17,
        10**18,
        2 * 10**18,
        5 * 10**18,
        10 * 10**18,
        50 * 10**18,
        100 * 10**18,
    ]:
        out.append({"name": f"sell-{amount}", "price": 176245, "amount": amount})
    for amount in [1, 10, 100, 1000, 5000, 10000, 50000, 100000]:
        out.append(
            {
                "name": f"buy-{amount}-usdc",
                "price": 176245,
                "amount": amount * 10**6,
                "reverse": True,
            }
        )
    for score in [0, 1, 2, 10, 20, 44, 100, 255]:
        out.append({"name": f"classifier-{score}", "price": 176245, "score": score})
    for age in [0, 1, 2, 3, 5, 10, 30, 60, 119, 120, 121, 255, 300]:
        out.append({"name": f"time-plus-{age}", "price": 176245, "time_delta": age})
    for units in [0, 1, 10, 30, 60, 100, 119, 120, 140]:
        out.append(
            {
                "name": f"inventory-{units}-lots",
                "price": 176245,
                "vault_weth": units * 6 * 10**17,
            }
        )
    for n in [1, 2, 3, 5]:
        out.append(
            {"name": f"prior-same-side-updates-{n}", "price": 176245, "updates": n}
        )
    for amounts in [[2 * 10**18], [10**18, 10**18], [10**18], [5 * 10**17, 5 * 10**17]]:
        out.append(
            {
                "name": "fixed-volume-" + "-".join(map(str, amounts)),
                "price": 176245,
                "update_amounts": amounts,
            }
        )
    out.append(
        {
            "name": "next-block-after-two-updates",
            "price": 176245,
            "update_amounts": [10**18, 10**18],
            "advance_block": True,
        }
    )
    return out


def experiment(spec, witness, header, fetch=None, dispatcher_code=None):
    overrides = {}
    old = int(witness[ENGINE]["storage"]["0x2"], 16)
    if spec.get("price") is not None:
        overrides = {
            ENGINE: {
                "0x2": hex((old & ~(((1 << 22) - 1) << 32)) | (spec["price"] << 32))
            }
        }
    if "vault_weth" in spec:
        overrides[WETH] = {
            "0x330aa97da5768f88ff69c73d742ba3f54398b4eeb88f35fdf81f0dea20c63a76": hex(
                spec["vault_weth"]
            )
        }
    codes = (
        {CLASSIFIER: "0x" + ret_word(spec["score"]).hex()} if "score" in spec else {}
    )
    if dispatcher_code is not None:
        codes["0x555a998a43a63d67abfb186b375d8aa56c66790b"] = (
            "0x" + dispatcher_code.hex()
        )
    vm = make_state(
        witness,
        header,
        overrides,
        codes,
        int(header["timestamp"], 16) + spec.get("time_delta", 0),
        fetch,
    )
    data = quote_data(spec.get("amount", 10**18), spec.get("reverse", False))
    c = invoke(vm, data)
    if c.is_error:
        return {
            "name": spec["name"],
            "reverted": True,
            "output": "0x" + c.output.hex(),
            "spec": spec,
        }
    amount, qid, extra = decode(["uint256", "uint256", "bytes"], c.output)
    before = amount
    updates = spec.get("update_amounts", [10**18] * spec.get("updates", 0))
    for update_amount in updates:
        q = invoke(vm, quote_data(update_amount))
        if q.is_error:
            raise AssertionError("Pre-update quote reverted")
        update_out, qid, extra = decode(["uint256", "uint256", "bytes"], q.output)
        update = bytes.fromhex("519341bb") + encode(
            [
                "uint256",
                "bytes",
                "address",
                "address",
                "uint256",
                "uint256",
                "address",
                "uint256",
            ],
            [qid, extra, WETH, USDC, update_amount, update_out, EXECUTOR, 0],
        )
        u = invoke(vm, update)
        if u.is_error:
            return {
                "name": spec["name"],
                "update_reverted": True,
                "output": "0x" + u.output.hex(),
                "spec": spec,
            }
        c = invoke(vm, data)
        if c.is_error:
            return {
                "name": spec["name"],
                "quote_after_update_reverted": True,
                "spec": spec,
            }
        amount, qid, extra = decode(["uint256", "uint256", "bytes"], c.output)
    changes = []
    if updates:
        for a, record in witness.items():
            for k, v in record["storage"].items():
                now = vm.state.get_storage(addr(a), int(k, 16))
                initial = int(overrides.get(a, {}).get(k, v), 16)
                if now != initial:
                    changes.append(
                        {
                            "address": a,
                            "slot": k,
                            "before": hex(initial),
                            "after": hex(now),
                        }
                    )
    if spec.get("advance_block"):
        next_witness = copy.deepcopy(witness)
        for change in changes:
            next_witness[change["address"]]["storage"][change["slot"]] = change["after"]
        next_header = dict(header, number=hex(int(header["number"], 16) + 1))
        vm = make_state(
            next_witness,
            next_header,
            overrides,
            codes,
            int(header["timestamp"], 16),
            fetch,
        )
        c = invoke(vm, data)
        if c.is_error:
            raise AssertionError("Next-block quote reverted")
        amount, qid, extra = decode(["uint256", "uint256", "bytes"], c.output)
    return {
        "changed_storage": changes,
        "name": spec["name"],
        "reverted": False,
        "amount": amount,
        "before_updates": before,
        "quote_id": hex(qid),
        "data": "0x" + extra.hex(),
        "spec": spec,
    }


def run_all(witness, header, fetch=None, dispatcher_code=None):
    return [experiment(s, witness, header, fetch, dispatcher_code) for s in scenarios()]
