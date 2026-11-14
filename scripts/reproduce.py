"""Compile and validate a case from any current working directory."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from evm_lab.verification import check_sources, verify_case

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case', nargs='?', default='wintermute-curve-balancer')
    args = p.parse_args()
    case = (ROOT/'cases'/args.case).resolve()
    if not case.is_relative_to(ROOT/'cases'):
        raise ValueError('Select a case within cases/')
    config = json.loads((case/'case.json').read_text())
    check_sources(case)
    output = ROOT/'build'/args.case
    artifact = output/'compiled.json'
    subprocess.run(['node',str(ROOT/'scripts/compile.cjs'),str(case/config['source_input']),
                    str(artifact),config['contract'],config['compiler']],check=True,cwd=ROOT)
    result = verify_case(case,artifact,output)
    if not result['passed']: raise RuntimeError('Bytecode or selector comparison failed; inspect build output')
    subprocess.run([sys.executable,str(case/'differential.py'),'--candidate',str(output/'candidate-runtime.hex'),
                    '--output',str(output/'differential-results.json')],check=True,cwd=ROOT)
    print(json.dumps({'case':args.case,'runtime_executable_match':result['runtime']['executable_match'],
                      'creation_executable_match':result['creation']['executable_match'],
                      'metadata_match':result['runtime']['metadata_match'],
                      'selectors':len(result['selectors']),'output':str(output)},indent=2))


if __name__ == '__main__': main()
