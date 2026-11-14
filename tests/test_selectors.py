import pytest
from eth_abi import encode
from evm_lab.selectors import selector, argument_types, decode_call, mine_name
from evm_lab.cli import main


def test_ethereum_keccak():
    assert selector('transfer(address,uint256)') == '0xa9059cbb'


def test_nested_tuple_array_decode():
    sig = 'approveBatch((address,uint256)[],bytes)'
    address = '0x'+'12'*20
    types = ['(address,uint256)[]','bytes']
    assert argument_types(sig) == types
    data = bytes.fromhex(selector(sig)[2:])+encode(types,[[(address,5)],b'abc'])
    assert decode_call(sig,data)['arguments'] == [[[address,5]],'0x616263']


def test_wrong_selector_rejected():
    with pytest.raises(ValueError): decode_call('foo()',bytes.fromhex('a9059cbb'))


def test_bounded_miner_provenance_and_resume():
    target = selector('recovered_3(address)')
    assert mine_name(target,'(address)',0,3)['next_start'] == 3
    hit = mine_name(target,'(address)',3,1)
    assert hit['found'] and hit['signature'] == 'recovered_3(address)'
    assert hit['provenance'] == 'synthetic_selector_collision'


def test_cli_reports_mismatch(tmp_path,capsys):
    a,b = tmp_path/'a.hex',tmp_path/'b.hex'
    a.write_text('6000'); b.write_text('6001')
    assert main(['compare',str(a),str(b)]) == 1
    assert 'false' in capsys.readouterr().out


def test_cli_empty_parameters(capsys):
    sig='foo()'
    assert main(['decode',sig,selector(sig)]) == 0
    assert '"arguments": []' in capsys.readouterr().out
