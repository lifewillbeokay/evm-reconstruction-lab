"""Independently verify synthetic signatures produced by the optional GPU miner."""
import json
import sys
from pathlib import Path
from evm_lab.selectors import selector

hits = json.loads(Path(sys.argv[1]).read_text())
if not hits: raise SystemExit('No hits to verify')
for expected, signature in hits.items():
    actual = selector(signature)
    if actual != '0x' + expected.removeprefix('0x').lower():
        raise SystemExit(f'Selector mismatch: {signature} -> {actual}, expected {expected}')
print(f'{len(hits)} selector collisions independently verified; original names remain unknown')
