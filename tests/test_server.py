import pytest
import asyncio
import websockets
import wsmprpc
from .websocket_simple_server import rpc_server

port = 8000

async def abnormal_closed_client():
    async with websockets.connect(f'ws://localhost:{port}') as ws, \
        wsmprpc.connect(ws) as stub:
        print('[client start]')
        async for x in stub.repeat('x', 4):
            break
    print('[client end]')



async def test_server():
    async with websockets.serve(rpc_server.run, "localhost", port):
        print('[server start]')
        await abnormal_closed_client()
        print('[server end]')
