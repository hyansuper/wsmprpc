import pytest
import threading
import asyncio
import websockets
import wsmprpc

port = 8080

@pytest.fixture
def abnormal_closed_client():
    async def abnormal_close():
        await asyncio.sleep(2)
        print('[client start]')
        async with websockets.connect(f'ws://localhost:{port}') as ws, \
            wsmprpc.connect(ws) as stub:
            async for x in stub.repeat('x', 4):
                break
        print('[client end]')
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    def run_loop(loop, coro):
        loop.run_until_complete(coro)
        loop.close()
    client_thread = threading.Thread(target=run_loop, args=(loop, abnormal_close()))
    client_thread.start()

from .websocket_simple_server import rpc_server
async def test_server(abnormal_closed_client):
    async with websockets.serve(rpc_server.run, "localhost", port):
        print('[server start]')
        await asyncio.sleep(5)
        print('[server end]')




