import pytest
import asyncio
import websockets
import wsmprpc
from .websocket_simple_server import rpc_server

port = 8000

@pytest.fixture(scope='module')
async def server():
    async with websockets.serve(rpc_server.run, "localhost", port):
        print('[server start]')
        yield
    print('[server stop]')

@pytest.fixture(scope='module')
async def stub(server):
    async with websockets.connect(f'ws://localhost:{port}') as ws, \
        wsmprpc.connect(ws) as stub:
        print('[client start]')
        yield stub
    print('[client stop]')

def test_rpc_info_doc(stub):
    assert stub.rpc_info[0] == ('div(a: float, b: float) -> float', 'Return a divided by b', False, False)

@pytest.mark.parametrize("fname, stream_type", [('delay_echo', (False, False)), ('uppercase', (True, True))])
def test_rpc_info_stream_type(stub, fname, stream_type):
    i = stub._fn_ls.index(fname)
    assert stub.rpc_info[i][-2:] == stream_type

async def test_non_async_rpc(stub):
    assert 2. == await stub.div(4, 2)

async def test_async_rpc(stub):
    assert 'echo' == await stub.delay_echo(0.1, 'echo')

async def test_rpc_with_keywords(stub):
    assert 'echo' == await stub.delay_echo(echo='echo', delay=.1)

async def test_request_stream(stub):
    assert 3 == await stub.sum(request_stream=range(3))

async def test_request_response_stream(stub):
    assert ['HELLO', 'RPC'] == [x async for x in stub.uppercase(request_stream=['hello', 'rpc'])]

async def test_rpc_err(stub):
    with pytest.raises(wsmprpc.RPCServerError) as err:
        await stub.div(1, 0)
    assert 'division by zero' in str(err.value)

async def test_wrong_param_err(stub):
    with pytest.raises(wsmprpc.RPCServerError) as err:
        await stub.div(1, 4, 5)

async def test_unknown_rpc_err(stub):
    with pytest.raises(wsmprpc.RPCClientError) as err:
        await stub.x(3)

async def test_cancel_after_started(stub):
    with pytest.raises(asyncio.CancelledError):
        echo = stub.delay_echo(1, 'echo')
        asyncio.get_running_loop().call_later(.5, echo.cancel)
        await echo

async def test_cancel_before_started(stub):
    with pytest.raises(asyncio.CancelledError):
        echo = stub.delay_echo(1, 'echo')
        await echo.async_cancel()
        await echo

async def test_response_stream_cancel_before_start(stub):
    with pytest.raises(asyncio.CancelledError):
        repeat = stub.repeat('wb', 3)
        repeat.cancel()
        async for w in repeat:
            print(w, end=' ')

async def test_response_stream_cancel_after_start(stub):
    with pytest.raises(asyncio.CancelledError):
        repeat = stub.repeat('wa', 4)
        asyncio.get_running_loop().call_later(1, repeat.cancel)
        async for w in repeat:
            print(w, end=' ')

async def test_request_stream_err(stub):
    with pytest.raises(wsmprpc.RPCClientError) as err:
        async for x in stub.repeat('a', 4, request_stream=[1,2,3]):
            pass

async def test_request_stream_err_2(stub):
    with pytest.raises(wsmprpc.RPCClientError) as err:
        await stub.uppercase(2)