from evm_lab.evm import Context, make_vm, execute, constructor_runtime, capture

A,B = bytes.fromhex('aa'*20),bytes.fromhex('bb'*20)


def test_initcode_returns_runtime():
    # Return one zero byte from memory.
    assert constructor_runtime(bytes.fromhex('60016000f3'),Context(A,B)) == b'\x00'


def test_revert_rolls_back_storage_and_value():
    context=Context(A,B)
    vm=make_vm(context)
    vm.state.set_balance(B,100)
    # SSTORE(0,1), then revert.
    computation=execute(vm,context,bytes.fromhex('600160005560006000fd'),value=7)
    result=capture(vm,computation,[(A,0)],[A,B])
    assert result['error'] and result['storage'][A.hex()+':0'] == 0
    assert result['balances'] == {A.hex():0,B.hex():100}


def test_success_commits_storage_and_value():
    context=Context(A,B)
    vm=make_vm(context); vm.state.set_balance(B,100)
    c=execute(vm,context,bytes.fromhex('600160005500'),value=7)
    assert not c.is_error
    assert vm.state.get_storage(A,0)==1 and vm.state.get_balance(A)==7
