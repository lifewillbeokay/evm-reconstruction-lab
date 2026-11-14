import cbor2
import pytest
from evm_lab.bytecode import parse_hex, split_metadata, compare, first_difference
from evm_lab.opcodes import disassemble, inspect


def metadata(values):
    raw = cbor2.dumps(values)
    return raw + len(raw).to_bytes(2, 'big')


@pytest.mark.parametrize('bad', ['0x1','zz','01 02','0x600g','0x-1'])
def test_reject_invalid_hex(bad):
    with pytest.raises(ValueError): parse_hex(bad)


def test_hex_prefix_and_empty():
    assert parse_hex('0x6000\n') == b'\x60\x00'
    assert parse_hex('0x') == b''


def test_metadata_hash_change_is_separate():
    a = b'\x60\x00\x00' + metadata({'solc':b'\x00\x08\x13','ipfs':b'a'*34})
    b = b'\x60\x00\x00' + metadata({'solc':b'\x00\x08\x13','ipfs':b'b'*34})
    assert split_metadata(a).executable == b'\x60\x00\x00'
    result = compare(a,b)
    assert result['executable_match'] and not result['exact_match'] and not result['metadata_match']


@pytest.mark.parametrize('suffix', [b'',b'\x00\x00',b'\x00\xff',b'\xff\x00\x01',metadata({'unrelated':1})])
def test_unknown_suffix_is_preserved(suffix):
    code = b'\x60\x00\x00' + suffix
    assert split_metadata(code).executable == code


def test_cbor_trailing_junk_not_stripped():
    payload = cbor2.dumps({'solc':b'\x00\x08\x13'})+b'\x00'
    code = b'\x00'+payload+len(payload).to_bytes(2,'big')
    assert split_metadata(code).metadata == b''


def test_prefix_length_difference():
    assert first_difference(b'\x60', b'\x60\x01') == 1
    assert compare(b'\x60', b'\x60\x01')['first_executable_difference'] == 1
    assert first_difference(b'',b'') is None


def test_disassembler_skips_push_data():
    code = bytes.fromhex('636312345663deadbeef00')
    candidates = inspect(code)['push4_candidates']
    assert candidates == [{'pc':0,'value':'0x63123456'},{'pc':5,'value':'0xdeadbeef'}]


def test_truncated_push_and_push0():
    ops = list(disassemble(bytes.fromhex('5f6360')))
    assert ops[0]['name'] == 'PUSH0'
    assert ops[1]['name'] == 'PUSH4' and ops[1]['truncated']
