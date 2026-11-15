"""Differential experiments for the small deployed fee helper, not the engine."""
import argparse
import copy
import hashlib
import json
import random
from pathlib import Path
from eth_abi import encode
from evm_lab.evm import Context, make_vm, execute

P = Path(__file__).resolve().parent
TARGET = bytes.fromhex((P/'evidence/helper-creation.hex').read_text().strip().removeprefix('0x'))[26:]
TOKEN = '0x4200000000000000000000000000000000000006'
POOL = bytes.fromhex('72ab388e2e2f6facef59e3c3fa2c4e29011c2d38')
ADDR = bytes.fromhex('42e88fbc20c66bfe4bac17892980b640990d8cbc')
CTX = Context(ADDR, bytes.fromhex('11'*20), timestamp=1800000000, chain_id=8453, fork='cancun')

def word(v):
    return (v % 2**256).to_bytes(32,'big')

def return_bytes(data):
    code = bytearray()
    for i in range(0,len(data),32):
        code += b'\x7f'+data[i:i+32].ljust(32,b'\0')+b'\x60'+bytes([i])+b'\x52'
    code += b'\x60'+bytes([len(data)])+b'\x5f\xf3'
    return code

def mock(case):
    code=bytearray.fromhex('3660041461000057600435')
    code += b'\x7f'+word(case['slot'][2])+b'\x14\x61\0\0\x57'
    previous = return_bytes(b''.join(word(x) for x in case['previous']))
    current = return_bytes(b''.join(word(x) for x in case['current']))
    slot = return_bytes(b''.join(word(x) for x in case['slot']))
    code[5:7] = (len(code)+len(previous)+len(current)+1).to_bytes(2,'big')
    code[-3:-1] = (len(code)+len(previous)).to_bytes(2,'big')
    return bytes(code+previous+b'\x5b'+current+b'\x5b'+slot)

def run(code, scenario):
    vm=make_vm(CTX)
    vm.state.set_code(POOL,mock(scenario))
    computation=execute(vm,CTX,code,bytes.fromhex('b88c9148')+encode(['address'],[scenario.get('token',TOKEN)]))
    return {'error':computation.is_error,'output':computation.output.hex(), 'calls':[
        {'to':c.msg.to.hex(),'data':c.msg.data_as_bytes.hex(),'error':c.is_error,'output':c.output.hex()}
        for c in computation.children]}

def run_all(candidate):
    baseline={'slot':[1,-200000,1,2], 'current':[CTX.timestamp,1000000,0,1], 'previous':[CTX.timestamp-2,1400000,0,1]}
    scenarios=[]
    def case(name,group=None,index=None,value=None,**fields):
        c=copy.deepcopy(baseline);c.update(fields);c['name']=name
        if group is not None:c[group][index]=value
        scenarios.append(c)
    case('unchanged-tick')
    for i in [-887273,-887272,-200101,-200099,-200010,-200001,-200000,-199999,-199990,0,887272,887273,2**255-1,-2**255]:case(f'tick-{i}','slot',1,i)
    for i in [0,1,2,65535,65536,2**255]:case(f'cardinality-{i}','slot',3,i)
    for i in [0,1,2,65535,65536,2**255]:case(f'index-{i}','slot',2,i)
    for group in ['current','previous']:
        for index,values in [(0,[0,CTX.timestamp-1,CTX.timestamp,CTX.timestamp+1,2**32+CTX.timestamp]),(1,[-2**55-1,-2**55,2**55-1,2**55,2**255-1]),(3,[0,1,2,2**255])]:
            for i in values:case(f'{group}-{index}-{i}',group,index,i)
    case('unsupported-token',token='0x'+'22'*20)
    random.seed(20261114)
    for i in range(100):
        tick=random.randint(-887272,887272);avg=tick+random.randint(-150,150);elapsed=random.randint(1,500);cumulative=random.randint(-2**53,2**53)
        case(f'random-{i}',slot=[1,tick,1,2],current=[CTX.timestamp,cumulative,0,1],previous=[CTX.timestamp-elapsed,cumulative-avg*elapsed,0,1])
    results=[]
    for scenario in scenarios:
        a=run(TARGET,scenario);b=run(candidate,scenario)
        results.append({'scenario':scenario,'target':a,'candidate':b,'match':a==b})
    return results


def compact(results):
    return [{"name":r["scenario"]["name"], "match":r["match"],
             "target_error":r["target"]["error"], "target_output":r["target"]["output"],
             "target_calls_sha256":hashlib.sha256(json.dumps(r["target"]["calls"], sort_keys=True).encode()).hexdigest()}
            for r in results]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    candidate = bytes.fromhex(args.candidate.read_text().strip().removeprefix('0x'))
    results = run_all(candidate)
    args.output.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({'total':len(results), 'matches':sum(r['match'] for r in results)}))
    assert all(r['match'] for r in results)
