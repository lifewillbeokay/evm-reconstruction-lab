"""Offline validation of the partial parent reconstruction, not full equivalence."""

import hashlib
import json
from eth_abi import encode
from eth_utils import keccak
import constructor_probe as p
from internal_probe import probe
from engine_lab import call_tree, ret_word
from evm_lab.bytecode import compare, parse_hex


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compact(results):
    return [
        {"name": r["name"], "match": r["match"], "target_sha256": digest(r["target"])}
        for r in results
    ]


def full_book_cases():
    """RPC-backed baseline plus explicit synthetic price, balance and fee changes."""
    data = bytes.fromhex("ba88b1cc") + encode(["address"], [p.ARGS[4][0]])
    out = [("captured-full-book", data, {})]
    witness = json.loads((p.CASE / "evidence/state-witness-getters.json").read_text())
    original = int(witness[p.ENGINE]["storage"]["0x2"], 16)
    now = int(p.HEADER["timestamp"], 16)
    for age in [-1, 0, 1, 6, 7, 8, 9, 10, 11, 15, 16, 100]:
        word = (original & ~((1 << 32) - 1)) | (now - age)
        out.append(
            (f"book-age-{age}", data, {"overrides": {p.ENGINE: {"0x2": hex(word)}}})
        )
    for price in [0, 1, 174400, 174413, 174425, 174500, (1 << 22) - 1]:
        for shift in [-32, 0, 31]:
            word = (original & ~(((1 << 28) - 1) << 32)) | (
                (price | ((shift & 63) << 22)) << 32
            )
            out.append(
                (
                    f"book-posted-{price}-{shift}",
                    data,
                    {"overrides": {p.ENGINE: {"0x2": hex(word)}}},
                )
            )
    for fee in [0, 10, 100, 1000, 1001]:
        out.append(
            (
                f"book-helper-{fee}",
                data,
                {"code": {p.HELPER: "0x" + ret_word(fee).hex()}},
            )
        )
    for code in ["0x", "0x5f5ffd"]:
        out.append(("book-helper-" + code, data, {"code": {p.HELPER: code}}))
    for balance in [0, 1, 6 * 10**17, 90 * 10**18]:
        for cash in [0, 1, 1000 * 10**6]:
            out.append(
                (
                    f"book-balances-{balance}-{cash}",
                    data,
                    {
                        "code": {
                            p.ARGS[4][0]: "0x" + ret_word(balance).hex(),
                            p.ARGS[2]: "0x" + ret_word(cash).hex(),
                        }
                    },
                )
            )
    key = hex(int.from_bytes(keccak(bytes(64)), "big"))
    for config in [0, 257, 1 << 232, (1 << 232) | 257]:
        out.append(
            (
                f"book-config-{config}",
                data,
                {"overrides": {p.ENGINE: {key: hex(config)}}},
            )
        )
    out.append(("book-owner-origin", data, {"origin": p.DEPLOYER}))
    return out


def run_all():
    # Artifacts must be compiled before importing the test-only harness modules.
    import state_differential as state
    import reference_constructor_probe as references
    import price_differential as prices
    import base_price_differential as bases
    import book_differential as books

    creation = bytes.fromhex(
        json.loads((p.BUILD / "state-compiled.json").read_text())["evm"]["bytecode"][
            "object"
        ]
    )
    results = []
    counts = {}

    def record(group, name, target, candidate):
        results.append(
            {
                "name": group + ":" + name,
                "match": target == candidate,
                "target": target,
                "candidate": candidate,
            }
        )
        counts[group] = counts.get(group, 0) + 1

    def constructor_result(args, code, extra=None):
        result, *_ = p.run(args, creation=code, extra_code=extra)
        result["storage"] = {k: v for k, v in result["storage"].items() if int(v, 16)}
        return result

    for name, args in p.scenarios():
        record(
            "constructor",
            name,
            constructor_result(args, p.ORIGINAL),
            constructor_result(args, creation),
        )
    for name, args, code in references.scenarios():
        record(
            "reference-constructor",
            name,
            constructor_result(args, p.ORIGINAL, code),
            constructor_result(args, creation, code),
        )
    for case in state.scenarios():
        record(
            "state",
            case["name"],
            state.run(p.ORIGINAL, case),
            state.run(creation, case),
        )
    for group, module in [
        ("price-primitives", prices),
        ("price-selection", bases),
        ("book-internals", books),
    ]:
        for name, args, kwargs in module.scenarios():
            r = prices.evaluate(*args, **kwargs)
            target = {
                "error": r["target_error"],
                "output": r["target"],
                "calls_match": True,
            }
            candidate = {
                "error": r["candidate_error"],
                "output": r["candidate"],
                "calls_match": r["calls_match"],
            }
            record(group, name, target, candidate)
    _, _, _, _, created = p.run(p.ARGS, creation=creation)
    assert not created.is_error
    runtime = "0x" + created.output.hex()
    match = compare(
        parse_hex((p.CASE / "chain-runtime.hex").read_text()), created.output
    )
    (p.BUILD / "parent-bytecode-match.json").write_text(
        json.dumps(match, indent=2) + "\n"
    )
    signatures = json.loads(
        (p.CASE / "evidence/constructed-selector-signatures.json").read_text()
    )
    for selector, signature in signatures.items():
        assert keccak(text=signature)[:4].hex() == selector
    for name, data, kwargs in full_book_cases():
        target, _, _ = probe(data=data, trace=False, **kwargs)
        candidate_kwargs = dict(kwargs)
        candidate_kwargs["code"] = {**kwargs.get("code", {}), p.ENGINE: runtime}
        candidate, _, _ = probe(data=data, trace=False, **candidate_kwargs)
        record("full-book", name, call_tree(target), call_tree(candidate))
        if name == "captured-full-book":
            fixture = json.loads(
                (p.CASE / "evidence/baseline-replays.json").read_text()
            )[0]
            assert "0x" + candidate.output.hex() == fixture["rpc_output"]
    return results, counts
