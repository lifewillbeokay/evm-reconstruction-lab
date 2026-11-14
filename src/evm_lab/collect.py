"""Read-only JSON-RPC collection with a pinned block and endpoint redaction."""
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from eth_utils import keccak
from .bytecode import parse_hex


class RPC:
    def __init__(self, url: str):
        if not url.startswith(("https://", "http://")):
            raise ValueError("RPC endpoint must use HTTP(S)")
        self.url = url

    def call(self, method, params):
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        try:
            with urlopen(Request(self.url, data=payload, headers={"Content-Type": "application/json"}), timeout=30) as r:
                body = json.load(r)
        except (URLError, OSError, ValueError):
            # Endpoint URLs often carry credentials. Never echo them or server bodies.
            raise ValueError(f"RPC {method} failed; check connectivity and endpoint configuration") from None
        if "error" in body or "result" not in body:
            raise ValueError(f"RPC {method} returned an error; provider may not support this request")
        return body["result"]


def collect(rpc, address: str, output: Path, block="latest", deployment_tx=None):
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
        raise ValueError("Expected a 20-byte contract address")
    address = address.lower()
    if output.exists():
        raise ValueError("Collection output must be a new directory")
    header = rpc.call("eth_getBlockByNumber", [block, False])
    if not header or not header.get("hash") or not header.get("number"):
        raise ValueError("Block must exist and be mined (pending is unsupported)")
    number = header["number"]
    runtime = parse_hex(rpc.call("eth_getCode", [address, number]))
    if not runtime:
        raise ValueError("No deployed code at this address and block")
    evidence = {"chain_id": int(rpc.call("eth_chainId", []), 16), "address": address,
                "block_number": int(number, 16), "block_hash": header["hash"],
                "runtime_keccak256": "0x" + keccak(runtime).hex(), "proxy_candidates": {}}
    files = {"chain-runtime.hex": runtime.hex() + "\n"}
    for kind in ("implementation", "beacon"):
        slot = int.from_bytes(keccak(text="eip1967.proxy." + kind), "big") - 1
        word = parse_hex(rpc.call("eth_getStorageAt", [address, hex(slot), number]))
        if len(word) != 32:
            raise ValueError("Invalid RPC storage word")
        if any(word):
            evidence["proxy_candidates"][kind] = "0x" + word[-20:].hex()
    # Canonical EIP-1167 runtime only; variants require manual inspection.
    if len(runtime) == 45 and runtime[:10].hex() == "363d3d373d3d3d363d73" and runtime[30:].hex() == "5af43d82803e903d91602b57fd5bf3":
        evidence["proxy_candidates"]["minimal_proxy_implementation"] = "0x" + runtime[10:30].hex()
    for kind, impl in evidence["proxy_candidates"].items():
        files[kind + ".hex"] = parse_hex(rpc.call("eth_getCode", [impl, number])).hex() + "\n"
    if deployment_tx:
        if not re.fullmatch(r"0x[0-9a-fA-F]{64}", deployment_tx):
            raise ValueError("Invalid deployment transaction hash")
        tx = rpc.call("eth_getTransactionByHash", [deployment_tx])
        receipt = rpc.call("eth_getTransactionReceipt", [deployment_tx])
        if not tx or not receipt or tx.get("to") is not None or (receipt.get("contractAddress") or "").lower() != address:
            raise ValueError("Not a direct creation of this address. Factory deployments require a creation trace.")
        if receipt.get("status") != "0x1" or int(receipt["blockNumber"], 16) > int(number, 16):
            raise ValueError("Deployment failed or is newer than the pinned block")
        files["chain-creation-input.hex"] = parse_hex(tx["input"]).hex() + "\n"
        evidence.update(deployment_transaction=deployment_tx, deployment_receipt=receipt, deployer=tx["from"])
    rechecked = rpc.call("eth_getBlockByNumber", [number, False])
    if not rechecked or rechecked["hash"] != header["hash"]:
        raise ValueError("Chain reorganized during collection; retry with a finalized block")
    evidence["limitations"] = ["Proxy slots are hints, not proof of delegation.",
        "Beacon addresses are collected but not resolved through implementation().",
        "Factory initcode, historical storage and traces are not automatically collected."]
    output.mkdir(parents=True)
    for name, content in files.items():
        (output / name).write_text(content)
    (output / "collection.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence
