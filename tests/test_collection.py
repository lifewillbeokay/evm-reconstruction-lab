import pytest
from evm_lab.collect import collect

ADDRESS='0x'+'11'*20
TX='0x'+'22'*32


class FakeRPC:
    def __init__(self,reorg=False,factory=False): self.reorg,self.factory,self.headers=reorg,factory,0
    def call(self,method,params):
        if method=='eth_getBlockByNumber':
            self.headers+=1
            return {'number':'0x64','hash':'0x'+('bb' if self.reorg and self.headers>1 else 'aa')*32}
        if method=='eth_chainId': return '0x1'
        if method=='eth_getCode':
            assert params[1]=='0x64'
            return '0x600000'
        if method=='eth_getStorageAt': return '0x'+'00'*32
        if method=='eth_getTransactionByHash':
            return {'to':ADDRESS if self.factory else None,'from':'0x'+'33'*20,'input':'0x600000'}
        if method=='eth_getTransactionReceipt':
            return {'contractAddress':ADDRESS,'status':'0x1','blockNumber':'0x32'}
        raise AssertionError(method)


def test_pins_block_and_records_creation(tmp_path):
    dest=tmp_path/'case'
    result=collect(FakeRPC(),ADDRESS,dest,deployment_tx=TX)
    assert result['block_number']==100 and result['chain_id']==1
    assert (dest/'chain-creation-input.hex').read_text()=='600000\n'


def test_reorg_leaves_no_partial_evidence(tmp_path):
    dest=tmp_path/'case'
    with pytest.raises(ValueError,match='reorganized'): collect(FakeRPC(reorg=True),ADDRESS,dest)
    assert not dest.exists()


def test_factory_input_not_treated_as_initcode(tmp_path):
    with pytest.raises(ValueError,match='creation trace'):
        collect(FakeRPC(factory=True),ADDRESS,tmp_path/'case',deployment_tx=TX)


def test_existing_directory_not_overwritten(tmp_path):
    with pytest.raises(ValueError,match='new directory'): collect(FakeRPC(),ADDRESS,tmp_path)
