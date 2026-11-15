"""Compare every byte of this captured parent/child creation layout.

The two metadata regions are identified structurally, not by suppressing all
differences in creation code. Runtime immutables are also checked after actually
executing the candidate constructor in the captured dependency fixture.
"""

import hashlib
from evm_lab.bytecode import compare, split_metadata


def analyze(original_init, candidate_artifact, original_child_init,
            original_child_runtime, candidate_child_init, candidate_child_runtime,
            original_runtime, deployed_runtime):
    candidate_init = bytes.fromhex(candidate_artifact["evm"]["bytecode"]["object"])
    candidate_template = bytes.fromhex(
        candidate_artifact["evm"]["deployedBytecode"]["object"]
    )
    # Captured layout: constructor, immutable placeholders/runtime, child initcode.
    prefix_size = 4364
    runtime_size = 24500
    assert len(original_init) == prefix_size + runtime_size + len(original_child_init)
    assert original_init[-len(original_child_init):] == original_child_init
    original_template = original_init[prefix_size:prefix_size + runtime_size]
    assert len(candidate_init) == prefix_size + len(candidate_template) + len(candidate_child_init)
    assert candidate_init[prefix_size:] == candidate_template + candidate_child_init
    assert len(candidate_template) == runtime_size
    assert original_child_init.endswith(original_child_runtime)
    assert candidate_child_init.endswith(candidate_child_runtime)
    child_prefix_size = len(original_child_init) - len(original_child_runtime)
    assert len(candidate_child_init) - len(candidate_child_runtime) == child_prefix_size

    ot, ct = split_metadata(original_template), split_metadata(candidate_template)
    oc, cc = split_metadata(original_child_runtime), split_metadata(candidate_child_runtime)
    for parts in [ot, ct, oc, cc]:
        assert parts.decoded is not None and parts.metadata
    assert len(ot.executable) == len(ct.executable)
    assert len(ot.metadata) == len(ct.metadata)
    assert len(oc.executable) == len(cc.executable)
    assert len(oc.metadata) == len(cc.metadata)

    regions = [
        ("parent_constructor", "executable", original_init[:prefix_size], candidate_init[:prefix_size]),
        ("parent_runtime", "executable", ot.executable, ct.executable),
        ("parent_metadata", "metadata", ot.metadata, ct.metadata),
        ("helper_constructor", "executable", original_child_init[:child_prefix_size], candidate_child_init[:child_prefix_size]),
        ("helper_runtime", "executable", oc.executable, cc.executable),
        ("helper_metadata", "metadata", oc.metadata, cc.metadata),
    ]
    assert b"".join(a for _, _, a, _ in regions) == original_init
    assert b"".join(b for _, _, _, b in regions) == candidate_init
    offset = 0
    segments = []
    for name, kind, original, candidate in regions:
        assert len(original) == len(candidate)
        segments.append({
            "name": name,
            "kind": kind,
            "offset": offset,
            "bytes": len(original),
            "exact_match": original == candidate,
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
            "different_byte_positions": [i for i, (a, b) in enumerate(zip(original, candidate)) if a != b],
        })
        offset += len(original)
    return {
        "creation_bytes": len(original_init),
        "candidate_creation_bytes": len(candidate_init),
        "all_creation_bytes_accounted_for": offset == len(original_init),
        "full_creation_match": original_init == candidate_init,
        "creation_executable_match": all(s["exact_match"] for s in segments if s["kind"] == "executable"),
        "segments": segments,
        "parent_runtime_template": compare(original_template, candidate_template),
        "parent_runtime_deployed": compare(original_runtime, deployed_runtime),
        "helper_runtime": compare(original_child_runtime, candidate_child_runtime),
        "scope": "Every creation byte is assigned to a checked region. Only the two recognized CBOR metadata regions are excluded from executable equality. Deployed parent comparison uses actual constructor output, including immutables.",
    }
