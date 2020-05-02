import asyncio, websockets
import sys
sys.path.append('../')
from wsrpc import RPCClient

async def main():
    async with websockets.connect('ws://localhost:8000') as ws:
        stub = RPCClient(ws)

        print(await stub.div(1, 3))
        print(await stub.sleep(1))

        # request stream
        print(await stub.count(request_stream=['a','bb','ccc']))

        # get response stream
        async for i in stub.repeat('bla', 4):
            print(i)

        # combine request stream and response stream
        async for i in stub.uppercase(request_stream=['hello', 'rpc']):
            print(i)


asyncio.run(main())