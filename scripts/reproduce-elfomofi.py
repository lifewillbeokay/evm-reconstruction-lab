"""Compile and validate the behavioral ElfomoFi case entirely offline."""

import copy, json, os, subprocess, sys
from pathlib import Path
from eth_abi import encode, decode
from eth_utils import keccak
from evm_lab.bytecode import parse_hex, compare
from evm_lab.evm import Context, constructor_runtime

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "cases/elfomofi-pricing"
BUILD = REPO / "build/elfomofi-pricing"
sys.path.insert(0, str(CASE))
from engine_lab import make_state, invoke, run_all, ENGINE, WETH, USDC, META
from model import decode_metadata, decode_prices, exact_input


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    info = json.loads((CASE / "case.json").read_text())
    inp = json.loads((CASE / "standard-input.json").read_text())
    for name, entry in inp["sources"].items():
        assert entry["content"] == (CASE / name).read_text(), (
            f"Stale Standard JSON: {name}"
        )
    env = dict(os.environ, SOLC_MODULE=str(REPO / "node_modules/solc-0.8.34"))
    subprocess.run(
        [
            "node",
            str(REPO / "scripts/compile.cjs"),
            str(CASE / "standard-input.json"),
            str(BUILD / "compiled.json"),
            info["contract"],
            info["compiler"],
        ],
        env=env,
        check=True,
    )
    artifact = json.loads((BUILD / "compiled.json").read_text())
    ctx = Context(
        parse_hex(info["address"]),
        parse_hex(info["deployer"]),
        chain_id=8453,
        fork="cancun",
    )
    original = parse_hex((CASE / "chain-runtime.hex").read_text())
    creation = parse_hex((CASE / "chain-creation-input.hex").read_text())
    args = parse_hex((CASE / "constructor-arguments.hex").read_text())
    assert constructor_runtime(creation, ctx) == original, (
        "Original initcode does not reproduce captured runtime"
    )
    assert "0x" + keccak(original).hex() == info["runtime_keccak256"]
    candidate = constructor_runtime(
        bytes.fromhex(artifact["evm"]["bytecode"]["object"]) + args, ctx
    )
    (BUILD / "candidate.hex").write_text(candidate.hex() + "\n")
    match = compare(original, candidate)
    (BUILD / "bytecode-match.json").write_text(json.dumps(match, indent=2) + "\n")
    subprocess.run(
        [
            sys.executable,
            str(CASE / "differential.py"),
            "--candidate",
            str(BUILD / "candidate.hex"),
            "--output",
            str(BUILD / "differential-results.json"),
        ],
        check=True,
    )
    w = json.loads((CASE / "evidence/state-witness.json").read_text())
    h = json.loads((CASE / "evidence/block.json").read_text())
    rpc = json.loads((CASE / "evidence/rpc-quote.json").read_text())
    tx = rpc["params"][0]
    for code in [None, candidate]:
        codes = {} if code is None else {info["address"]: "0x" + code.hex()}
        vm = make_state(copy.deepcopy(w), h, code_overrides=codes)
        c = invoke(
            vm, parse_hex(tx["data"]), to=tx["to"], sender=tx["from"], origin=tx["from"]
        )
        assert not c.is_error and "0x" + c.output.hex() == rpc["result"], (
            "Historical RPC replay differs"
        )
    experiments = run_all(copy.deepcopy(w), h)
    expected = json.loads((CASE / "expected/engine-experiments.json").read_text())
    assert experiments == expected, "Engine experiment changed"
    assert run_all(copy.deepcopy(w), h, dispatcher_code=candidate) == experiments, (
        "Reconstructed dispatcher changed an engine experiment"
    )
    (BUILD / "engine-experiments.json").write_text(
        json.dumps(experiments, indent=2) + "\n"
    )
    # Validate recovered storage layout independently against the actual getter.
    vm = make_state(copy.deepcopy(w), h)
    meta = invoke(
        vm,
        keccak(text="getMetadata(address)")[:4] + encode(["address"], [WETH]),
        to=ENGINE,
    )
    words = [int(w[ENGINE]["storage"][hex(META + i)], 16) for i in range(3)]
    assert not meta.is_error and decode(
        ["uint256"] * 13, meta.output
    ) == decode_metadata(words)
    timestamp, prices = decode_prices(int(w[ENGINE]["storage"]["0x2"], 16))
    assert prices[0].mantissa == 0
    # Reproduce the counterfactual book; no offchain-model assumptions are hidden.
    word = int(w[ENGINE]["storage"]["0x2"], 16)
    overrides = {ENGINE: {"0x2": hex(word | (176245 << 32))}}
    vm = make_state(copy.deepcopy(w), h, overrides)
    c = invoke(
        vm, bytes.fromhex("0a6e04cb") + encode(["address", "address"], [WETH, USDC])
    )
    book = decode(["(uint256,uint256)[]", "(uint256,uint256)[]"], c.output)
    assert json.loads(json.dumps(book)) == json.loads(
        (CASE / "expected/counterfactual-orderbook.json").read_text()
    )
    arithmetic = 0
    for e in experiments:
        if e["name"].startswith(("buy-", "sell-")):
            buy = e["spec"].get("reverse", False)
            assert (
                exact_input(book[1 if buy else 0], e["spec"]["amount"], buy_base=buy)
                == e["amount"]
            ), e["name"]
            arithmetic += 1
    # Assertions describe behaviors, not just stored output snapshots.
    by = {e["name"]: e for e in experiments}
    assert by["anchor-175000"]["amount"] == by["anchor-177000"]["amount"] == 0
    assert (
        by["time-plus-5"]["amount"] < by["time-plus-0"]["amount"]
        and by["time-plus-30"]["amount"] == 0
    )
    assert by["classifier-2"]["amount"] < by["classifier-0"]["amount"]
    assert by["inventory-120-lots"]["amount"] == 0
    assert by["prior-same-side-updates-1"]["amount"] < by["anchor-176245"]["amount"]
    assert by["next-block-after-two-updates"]["amount"] == by["anchor-176245"]["amount"]
    one_large = by["fixed-volume-2000000000000000000"]["amount"]
    two_small = by["fixed-volume-1000000000000000000-1000000000000000000"]["amount"]
    assert one_large - two_small == 3
    assert one_large < by["fixed-volume-1000000000000000000"]["amount"]
    report = {
        "original_initcode_runtime_exact": True,
        "dispatcher_differential_cases": json.loads(
            (BUILD / "differential-results.json").read_text()
        )["total"],
        "historical_rpc_replays": 2,
        "engine_scenarios": len(experiments),
        "engine_scenarios_with_candidate_dispatcher": len(experiments),
        "independent_ladder_arithmetic_matches": arithmetic,
        "metadata_getter_matches": True,
        "exact_bytecode_match": match["exact_match"],
        "executable_bytecode_match": match["executable_match"],
        "explorer_submission": "not submitted",
        "scope": "Dispatcher behavioral reconstruction; original engine bytes used for bounded experiments. Engine source and upstream trading model are not fully recovered.",
    }
    (BUILD / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
