"""Compare compiled candidates against a case's captured deployment evidence."""
import json
from pathlib import Path
from .bytecode import compare, parse_hex, read_hex
from .evm import Context, constructor_runtime
from .selectors import selector


def inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Case paths must stay within their case directory")
    return path


def case_context(case: Path) -> Context:
    config = json.loads((case / "case.json").read_text())
    if config.get("constructor_value", 0) != 0:
        raise ValueError("Default constructor harness supports zero-value deployments only")
    return Context(address=parse_hex(config["address"]), sender=parse_hex(config["deployer"]),
                   timestamp=config["timestamp"], chain_id=config["chain_id"], fork=config["evm_fork"])


def check_sources(case: Path):
    config = json.loads((case / "case.json").read_text())
    standard = json.loads(inside(case, config["source_input"]).read_text())
    for name, item in standard["sources"].items():
        if "content" not in item or inside(case, name).read_text() != item["content"]:
            raise ValueError(f"Source differs from Standard JSON input: {name}")


def verify_case(case: Path, artifact_path: Path, output: Path) -> dict:
    check_sources(case)
    config = json.loads((case / "case.json").read_text())
    artifact = json.loads(artifact_path.read_text())
    context = case_context(case)
    args = read_hex(inside(case, config["constructor_arguments"]))
    original_input = read_hex(inside(case, config["chain_creation_input"]))
    original_runtime = read_hex(inside(case, config["chain_runtime"]))
    if args and not original_input.endswith(args):
        raise ValueError("Constructor arguments are not a suffix of the deployment input")
    original_creation = original_input[:-len(args)] if args else original_input
    reproduced = constructor_runtime(original_input, context)
    if reproduced != original_runtime:
        raise ValueError("Original initcode does not reproduce recorded runtime in synthetic state")
    candidate_creation = parse_hex(artifact["evm"]["bytecode"]["object"])
    candidate_runtime = constructor_runtime(candidate_creation + args, context)
    # Published case maps are assertions about selector-compatible signatures.
    selector_results = []
    selector_map = case / "selector-map.json"
    if selector_map.exists():
        identifiers = artifact["evm"]["methodIdentifiers"]
        for row in json.loads(selector_map.read_text()):
            signature, target = row["signature"], row["selector"].lower()
            selector_results.append({"selector": target, "signature": signature,
                "match": selector(signature) == target and identifiers.get(signature) == target[2:]})
        if len(selector_results) != len(identifiers):
            raise ValueError("Selector map does not cover the compiled interface")
    result = {"original_creation_reproduces_runtime": True,
              "runtime": compare(original_runtime, candidate_runtime),
              "creation": compare(original_creation, candidate_creation),
              "selectors": selector_results,
              "constructor_context": "synthetic empty state; zero value; explicit address, sender, timestamp, chain and fork"}
    result["passed"] = (result["runtime"]["executable_match"] and result["creation"]["executable_match"]
                        and all(x["match"] for x in selector_results))
    output.mkdir(parents=True, exist_ok=True)
    (output / "candidate-runtime.hex").write_text(candidate_runtime.hex() + "\n")
    (output / "match.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
