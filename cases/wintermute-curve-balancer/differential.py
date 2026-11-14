"""62 original-versus-candidate cases with synthetic venues and token contracts.

This is not a historical-state replay. Watchlisted storage, balances, logs, return
data and nested calls are compared. Gas and all possible states are not covered.
"""
from pathlib import Path
import argparse
import json
from dataclasses import replace
from eth_utils import keccak
from eth_abi import encode, decode
from evm_lab.bytecode import read_hex
from evm_lab.evm import Context, make_vm, execute, capture, mapping_slot as slot

ROOT = Path(__file__).resolve().parent
BOT = bytes.fromhex('ec6fc9be2d5e505b40a2df8b0622cd25333823db')
INV = bytes.fromhex('51c72848c68a965f66fa7a88855f9f7784502a7f')
OWNER = bytes.fromhex('ce466fc694c971b95bb1193e494942e22197f759')
REGISTRY = bytes.fromhex('7ff4ed8ab94c849b812622eb462682208be06b93')
WETH = bytes.fromhex('c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2')
VAULT = bytes.fromhex('ba12222222228d8ba445958a75a0704d566bf2c8')
CALLER, COINBASE, POOL, TOKEN, TOKEN_OUT = [bytes([n]) * 20 for n in [0x11, 0x22, 0x33, 0x44, 0x55]]
POOL_ID = bytes.fromhex('66' * 32)
NOW = 1794681755
CONTEXT = Context(BOT, CALLER, timestamp=NOW, coinbase=COINBASE, gas=10_000_000)
ROLES = {
    'operator':'50bd042dce90a5f0c1e33b44d95fd2c944e96f9d6be45bffae0d6c77ec711f4a',
    'curve':'54823ecad1e5445a9de111f3d8b0c63e51c0fc62cbe5692cb23e4e6da2250cbf',
    'coinbase':'cd5e156b3b60ca632455aa361bb28c1ad131c0050790057278c334308b9eae2a',
    'spender':'8a86140c2df97ed57d0d23317d04e2381eaf3b7477eb2c24abd4c921f473bfca',
    'balv1':'202f55c021fba7fb6834611facfd6443d7b984ab0b2a7985e89ad5e1dc96b0af',
    'balv2':'47ae38ccf90de8127449ca7ff05a9f876fb5c58a389e7bd013f98540dbde7b76',
    'unknown':'77' * 32,
}


def returns(n, second=None):
    code = b'\x7f' + n.to_bytes(32, 'big') + bytes.fromhex('600052')
    if second is not None:
        return code + b'\x7f' + second.to_bytes(32, 'big') + bytes.fromhex('60205260406000f3')
    return code + bytes.fromhex('60206000f3')


def fixture(code, active=True, operator=True, allowed_pool=True, allowed_builder=True,
            builder_reverts=False, token_in_reverts=False, token_out_reverts=False):
    vm = make_vm(CONTEXT); s = vm.state
    s.set_code(BOT, code); s.set_balance(BOT, 10**20)
    s.set_storage(BOT, 0, int(active))
    for key, base, allowed in [(CALLER,1,operator),(COINBASE,2,allowed_builder),
                               (POOL,3,allowed_pool),(POOL,4,allowed_pool),(POOL_ID,5,allowed_pool)]:
        s.set_storage(BOT, slot(key, base), int(allowed))
    revert = bytes.fromhex('60006000fd')
    s.set_code(TOKEN, revert if token_in_reverts else returns(1))
    s.set_code(TOKEN_OUT, revert if token_out_reverts else returns(987654321))
    s.set_code(WETH, returns(123456789)); s.set_code(POOL, returns(123456789,123))
    s.set_code(VAULT, returns(123456789))
    if builder_reverts: s.set_code(COINBASE, revert)
    return vm


def storage_set(vm, base, items):
    vm.state.set_storage(BOT, base, len(items))
    loc = int.from_bytes(keccak(base.to_bytes(32, 'big')), 'big')
    for i, value in enumerate(items):
        vm.state.set_storage(BOT, loc+i, int.from_bytes(value, 'big'))
        vm.state.set_storage(BOT, slot(value, base+1), i+1)


def run(original, candidate):
    cases, observed = [], {}
    def one(code, sel, types, args, caller, setup, settings):
        vm = fixture(code, **settings)
        if setup: setup(vm)
        c = execute(vm, replace(CONTEXT, sender=caller), code, bytes.fromhex(sel)+encode(types,args))
        keys = list(range(10)) + [slot(v,n) for v in [CALLER,TOKEN,POOL,POOL_ID,COINBASE] for n in range(1,10)]
        keys += [int.from_bytes(keccak(base.to_bytes(32,'big')),'big')+i for base in [6,8] for i in range(3)]
        return capture(vm,c,[(BOT,k) for k in keys],[BOT,CALLER,POOL,COINBASE,INV,TOKEN,TOKEN_OUT,WETH,VAULT])
    def test(name,sel,types,args,caller=CALLER,setup=None,**settings):
        a = one(original,sel,types,args,caller,setup,settings)
        b = one(candidate,sel,types,args,caller,setup,settings)
        observed[name] = a
        cases.append({'name':name,'match':a==b,**({} if a==b else {'original':a,'candidate':b})})
    A,U,I = 'address','uint256','int128'
    for role,val in ROLES.items():
        def setup(vm):
            vm.state.set_code(POOL,returns(int.from_bytes(POOL_ID,'big')))
            vm.state.set_code(VAULT,returns(int.from_bytes(POOL,'big'),0))
        test('grant_'+role,'cf1346bc',['bytes32',A,'bytes'],[bytes.fromhex(val),POOL,b''],REGISTRY,setup)
        test('revoke_absent_'+role,'59733e7f',['bytes32',A,'bytes'],[bytes.fromhex(val),POOL,b''],REGISTRY,setup)
    for specialization in [0,2,3,255,256]:
        def setup(vm, value=specialization): vm.state.set_code(VAULT,returns(int.from_bytes(POOL,'big'),value))
        test('pool_specialization_'+str(specialization),'534c83e5',['bytes32'],[POOL_ID],setup=setup)
    for token_code,kind in [(returns(1),'allowance_nonzero'),(returns(0),'allowance_zero'),(bytes.fromhex('60006000fd'),'allowance_revert'),(b'','allowance_empty')]:
        def setup(vm, code=token_code):
            storage_set(vm,6,[POOL]); storage_set(vm,8,[TOKEN]); vm.state.set_code(TOKEN,code)
        test('revoke_spender_'+kind,'59733e7f',['bytes32',A,'bytes'],[bytes.fromhex(ROLES['spender']),POOL,b''],REGISTRY,setup)
        test('revoke_count_'+kind,'f203c1b1',[U],[1],CALLER,setup)
        test('revoke_all_'+kind,'a5fd3043',[],[],CALLER,setup)
    for n in [0,1,2]: test('revoke_empty_'+str(n),'f203c1b1',[U],[n])
    test('approve_empty','3cbe46f8',['(address,address,uint256)[]'],[[]],OWNER)
    def approve_setup(vm): storage_set(vm,6,[POOL]); vm.state.set_code(TOKEN,returns(0))
    test('approve_token','3cbe46f8',['(address,address,uint256)[]'],[[(POOL,TOKEN,0)]],OWNER,approve_setup)
    test('transfer_token','2c88026b',[A+'[]',U+'[]',A],[[TOKEN],[13],POOL],OWNER)
    test('transfer_eth','8f05e71b',[U,A],[13,POOL],OWNER)
    test('kill','1c02708d',[],[])
    test('unkill','6b410e34',[],[],OWNER,active=False)
    test('eth_input_without_deadline','fc8b5d11',[U,A,I,I,U,U,A],[0,POOL,2,0,12345,1,TOKEN_OUT])
    curve_t = [U,A,U,U,U,U,A,A]; curve_a = [1000,POOL,2,0,12345,123000000,TOKEN,TOKEN_OUT]
    test('curve_uint','15427b54',curve_t,curve_a)
    for name,options in [('inactive',{'active':False}),('unauthorized_operator',{'operator':False}),
        ('unapproved_pool',{'allowed_pool':False}),('unapproved_builder',{'allowed_builder':False}),
        ('builder_reverts',{'builder_reverts':True}),('input_transfer_reverts',{'token_in_reverts':True}),
        ('output_token_reverts',{'token_out_reverts':True})]:
        test(name,'15427b54',curve_t,curve_a,**options)
    test('zero_tip_unapproved_builder','15427b54',curve_t,[0]+curve_a[1:],allowed_builder=False)
    test('curve_uint_deadline','6440a7b4',curve_t+[U],curve_a+[NOW+3])
    test('expired_deadline','6440a7b4',curve_t+[U],curve_a+[NOW-1])
    test('deadline_equal_now','6440a7b4',curve_t+[U],curve_a+[NOW])
    int_t = [U,A,I,I,U,U,A,A]
    test('curve_int_balance','cc5b1926',int_t,curve_a)
    test('curve_int_balance_deadline','cd6cf919',int_t+[U],curve_a+[NOW+3])
    ret_t = [U,A,I,I,U,U,'bool',A,A]; ret_a = curve_a[:6]+[False]+curve_a[6:]
    test('curve_int_return','c94ba2ba',ret_t,ret_a)
    test('curve_int_return_wrap_eth','c94ba2ba',ret_t,ret_a[:6]+[True]+ret_a[7:])
    test('curve_int_return_deadline','6d623b01',ret_t+[U],ret_a+[NOW+3])
    test('curve_eth_in_deadline','f1fe2eeb',[U,A,I,I,U,U,A,U],curve_a[:6]+[TOKEN_OUT,NOW+3])
    bal_t = [U,A,A,A,U,U,U]; bal_a = [1000,POOL,TOKEN,TOKEN_OUT,12345,123000000,2**255]
    test('balancer_v1','07f49f73',bal_t,bal_a)
    test('balancer_v1_deadline','8b8c1618',bal_t+[U],bal_a+[NOW+3])
    test('balancer_v2','cbc1e60c',[U,'bytes32',A,A,U,U,U],[1000,POOL_ID,TOKEN,TOKEN_OUT,12345,123000000,NOW+3])
    # Independent expectations prevent two equally broken executions from passing.
    for name,reason in [('inactive','C1'),('unauthorized_operator','C4'),('unapproved_pool','C7'),('unapproved_builder','C17'),('expired_deadline','C8')]:
        assert observed[name]['error'] and decode(['string'],bytes.fromhex(observed[name]['output'])[4:])[0] == reason
    for name in ['curve_uint','curve_uint_deadline','curve_int_balance','curve_int_balance_deadline',
                 'curve_int_return','curve_int_return_deadline','curve_int_return_wrap_eth',
                 'curve_eth_in_deadline','eth_input_without_deadline','balancer_v1','balancer_v1_deadline',
                 'balancer_v2','zero_tip_unapproved_builder','builder_reverts','deadline_equal_now']:
        assert not observed[name]['error'], name
    for name in ['curve_uint','curve_uint_deadline','curve_int_balance','curve_int_balance_deadline']:
        output_transfer = observed[name]['calls'][3]
        assert decode([A,U],bytes.fromhex(output_transfer['data'])[4:]) == ('0x'+INV.hex(),987654321)
    for name in ['curve_int_return','curve_int_return_deadline','balancer_v1','balancer_v1_deadline']:
        assert decode([A,U],bytes.fromhex(observed[name]['calls'][2]['data'])[4:]) == ('0x'+INV.hex(),123456789)
    expected = json.loads((ROOT/'expected/differential-results.json').read_text())
    assert {c['name'] for c in cases} == {c['name'] for c in expected}
    assert len(cases) == 62
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = run(read_hex(ROOT/'chain-runtime.hex'),read_hex(args.candidate))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    failed = [c['name'] for c in result if not c['match']]
    print(json.dumps({'cases':len(result),'passed':len(result)-len(failed),'failed':failed}))
    raise SystemExit(bool(failed))
