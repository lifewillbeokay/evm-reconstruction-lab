import argparse
import json
import os
import sys
from pathlib import Path
from .bytecode import read_hex, compare, parse_hex
from .opcodes import inspect, disassemble
from .selectors import selector, decode_call, mine_name
from .verification import verify_case, inside
from .collect import RPC, collect


def main(argv=None):
    p = argparse.ArgumentParser(description="EVM reconstruction primitives; no transaction broadcasting")
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("inspect", help="Metadata and PUSH4 candidates (not a recovered ABI)")
    q.add_argument("bytecode", type=Path)
    q = sub.add_parser("disassemble", help="Linear opcode listing, including embedded data")
    q.add_argument("bytecode", type=Path)
    q = sub.add_parser("compare", help="Report exact and metadata-separated bytecode matches")
    q.add_argument("original", type=Path); q.add_argument("candidate", type=Path)
    q.add_argument("--require", choices=["exact", "executable"], default="executable")
    q = sub.add_parser("selector", help="Hash a canonical signature with Ethereum Keccak")
    q.add_argument("signature")
    q = sub.add_parser("decode", help="Decode calldata using an explicitly supplied signature")
    q.add_argument("signature"); q.add_argument("calldata", help="Hex calldata, or @path to a hex file")
    q = sub.add_parser("mine-name", help="Bounded synthetic selector-collision search; does not recover names")
    q.add_argument("target"); q.add_argument("suffix", help="Canonical argument suffix, e.g. (address,uint256)")
    q.add_argument("--start", type=int, default=0); q.add_argument("--attempts", type=int, default=100000)
    q = sub.add_parser("collect", help="Read-only RPC snapshot at a pinned block")
    q.add_argument("address"); q.add_argument("--output", type=Path, required=True)
    q.add_argument("--rpc-env", default="ETH_RPC_URL", help="Environment variable containing endpoint; endpoint is not saved")
    q.add_argument("--block", default="finalized", help="RPC tag or hexadecimal block number")
    q.add_argument("--deployment-tx")
    q = sub.add_parser("verify", help="Execute constructors and compare against a recorded case")
    q.add_argument("case", type=Path); q.add_argument("--artifact", type=Path, required=True)
    q.add_argument("--output", type=Path, required=True)
    q = sub.add_parser("build-input", help="Refresh literal sources in a Standard JSON template")
    q.add_argument("template", type=Path); q.add_argument("--root", type=Path, required=True)
    q.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    status = 0
    try:
        match args.command:
            case "inspect": result = inspect(read_hex(args.bytecode))
            case "disassemble": result = list(disassemble(read_hex(args.bytecode)))
            case "compare":
                result = compare(read_hex(args.original), read_hex(args.candidate))
                status = 0 if result[args.require + "_match"] else 1
            case "selector": result = {"selector": selector(args.signature), "signature": args.signature}
            case "decode":
                data = read_hex(args.calldata[1:]) if args.calldata.startswith("@") else parse_hex(args.calldata)
                result = decode_call(args.signature, data)
            case "mine-name":
                result = mine_name(args.target, args.suffix, args.start, args.attempts)
                status = 0 if result["found"] else 1
            case "collect":
                endpoint = os.environ.get(args.rpc_env)
                if not endpoint: raise ValueError(f"Set {args.rpc_env} to your JSON-RPC endpoint")
                result = collect(RPC(endpoint), args.address, args.output, args.block, args.deployment_tx)
            case "verify":
                result = verify_case(args.case, args.artifact, args.output)
                status = 0 if result["passed"] else 1
            case "build-input":
                standard = json.loads(args.template.read_text())
                for name in standard["sources"]:
                    standard["sources"][name] = {"content": inside(args.root, name).read_text()}
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(standard, indent=2) + "\n")
                result = {"output": str(args.output), "sources": len(standard["sources"])}
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
