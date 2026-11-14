"""Write or check a SHA-256 manifest of committed case files."""
import argparse
import hashlib
import json
from pathlib import Path


def manifest(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()
            and p.name != 'manifest.json' and '__pycache__' not in p.parts}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case',type=Path); p.add_argument('--write',action='store_true')
    args = p.parse_args(); actual = manifest(args.case)
    path = args.case/'manifest.json'
    if args.write: path.write_text(json.dumps(actual,indent=2)+'\n')
    else:
        expected = json.loads(path.read_text())
        if actual != expected: raise SystemExit('Case manifest mismatch: added, missing, or modified files')
    print(f'{len(actual)} case files: manifest {"written" if args.write else "verified"}')
