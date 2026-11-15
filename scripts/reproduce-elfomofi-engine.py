"""Reproduce the current-engine checkpoint offline; does not claim full source recovery."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

from eth_abi import decode, encode
from eth_utils import keccak
from evm_lab.bytecode import compare, parse_hex
from evm_lab.evm import Context, constructor_runtime

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases/elfomofi-engine-84cb"
BUILD = REPO / "build/elfomofi-engine-checkpoint"
sys.path.insert(0, str(REPO / "cases/elfomofi-pricing"))
sys.path.insert(0, str(CASE))
from engine_lab import make_state, invoke, quote_data, ret_word, WETH
from helper_differential import run_all, compact


def read(path):
    return json.loads((CASE / path).read_text())


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    info = read("case.json")
    engine, helper = info["address"], info["helper"]
    header = read("evidence/block.json")
    witness = read("evidence/state-witness.json")
    original = parse_hex((CASE / "chain-runtime.hex").read_text())
    assert "0x" + keccak(original).hex() == info["runtime_keccak256"]
    helper_evidence = read("evidence/helper-chain-evidence.json")
    helper_runtime = parse_hex(helper_evidence["results"]["helper-code"])
    helper_init = parse_hex((CASE / "evidence/helper-creation.hex").read_text())
    ctx = Context(parse_hex(helper), parse_hex(engine), chain_id=8453, fork="cancun")
    assert constructor_runtime(helper_init, ctx) == helper_runtime

    # Native B20 behavior is an explicit, narrowly scoped fixture. Bytecode
    # remains 0xef, so EXTCODESIZE/EXTCODEHASH still see the captured code.
    native = read("evidence/native-decimals.json")
    native_calls = []

    def native_decimals(c):
        if not (c.msg.is_static and c.msg.value == 0
                and c.msg.sender == parse_hex(engine)
                and c.msg.data_as_bytes == parse_hex(native["call"]["data"])):
            raise ValueError("Uncaptured native B20 call")
        native_calls.append(c.msg.data_as_bytes.hex())
        c.output = parse_hex(native["result"])
        return c

    creation_witness = read("evidence/constructor-witness.json")
    assert creation_witness[engine]["code"] == (CASE / "chain-creation-input.hex").read_text().strip()
    vm = make_state(copy.deepcopy(creation_witness), header,
                    precompiles={parse_hex(native["call"]["to"]): native_decimals})
    # A newly created contract's starting nonce is one (EIP-161).
    vm.state.set_nonce(parse_hex(engine), 1)
    creator = read("evidence/deployment.json")["transaction"]["from"]
    creation = invoke(vm, b"", to=engine, sender=creator, origin=creator)
    assert not creation.is_error and creation.output == original
    assert vm.state.get_code(parse_hex(helper)) == helper_runtime
    assert native_calls == ["313ce567"]

    input_json = read("helper-standard-input.json")
    for path, entry in input_json["sources"].items():
        assert entry["content"] == (CASE / path).read_text()
    env = dict(os.environ, SOLC_MODULE=str(REPO / "node_modules/solc-0.8.34"))
    subprocess.run(["node", str(REPO / "scripts/compile.cjs"),
                    str(CASE / "helper-standard-input.json"), str(BUILD / "helper.json"),
                    "src/FeeHelper.sol:FeeHelper", info["compiler"]], env=env, check=True)
    artifact = json.loads((BUILD / "helper.json").read_text())
    candidate = constructor_runtime(bytes.fromhex(artifact["evm"]["bytecode"]["object"]), ctx)
    assert candidate == bytes.fromhex(artifact["evm"]["deployedBytecode"]["object"])
    match = compare(helper_runtime, candidate)
    (BUILD / "helper-bytecode-match.json").write_text(json.dumps(match, indent=2) + "\n")
    results = run_all(candidate)
    assert all(r["match"] for r in results), "Helper differential mismatch"
    assert compact(results) == read("expected/helper-differential.json")
    (BUILD / "helper-differential.json").write_text(json.dumps(results, indent=2) + "\n")

    baseline = read("evidence/baseline-replays.json")
    # Compare both the original helper and the reconstructed helper in the full
    # original engine's quote/book paths. This does not reconstruct the parent.
    for overrides in [{}, {helper: "0x" + candidate.hex()}]:
        vm = make_state(copy.deepcopy(witness), header, code_overrides=overrides)
        for request in baseline:
            c = invoke(vm, parse_hex(request["data"]), to=request["to"])
            assert not c.is_error and "0x" + c.output.hex() == request["rpc_output"]

    experiments = []
    for fee in [0, 10, 20, 100, 500, 1000, 1001, 2**256-1]:
        vm = make_state(copy.deepcopy(witness), header,
                        code_overrides={helper: "0x" + ret_word(fee).hex()})
        book = invoke(vm, bytes.fromhex("ba88b1cc") + encode(["address"], [WETH]), to=engine)
        assert not book.is_error
        bid, ask = decode(["(uint256,uint256)[]", "(uint256,uint256)[]"], book.output)
        sell = invoke(vm, quote_data(amount=10**16))
        buy = invoke(vm, quote_data(amount=10**16, reverse=True, exact_out=True))
        assert not sell.is_error and not buy.is_error
        experiments.append({"helperFee": fee, "bid": list(bid[0]), "ask": list(ask[0]),
                            "sell": decode(["uint256", "uint256", "bytes"], sell.output)[0],
                            "buy": decode(["uint256", "uint256", "bytes"], buy.output)[0]})
    assert experiments == read("expected/helper-parent-experiments.json")
    report = {"original_constructor_runtime_match": True,
              "constructor_scope": read("evidence/constructor-replay.json"),
              "helper_bytecode_match": match,
              "helper_differential_scenarios": len(results),
              "rpc_backed_replays_per_helper": len(baseline),
              "parent_adjustment_scenarios": len(experiments),
              "full_engine_source_reconstructed": False,
              "explorer_submission": "not submitted"}
    (BUILD / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"helper_scenarios": len(results), "constructor_runtime_match": True,
                      "rpc_replays": len(baseline) * 2, "parent_adjustments": len(experiments),
                      "full_engine_source_reconstructed": False}))


if __name__ == "__main__":
    main()
