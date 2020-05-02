import asyncio, websockets
import sys
sys.path.append('../')
from wsrpc import RPCClient

async def main():
    async with websockets.connect('ws://localhost:8000') as ws:
        stub = RPCClient(ws)

        # cancel normal function:
        s = stub.sleep(3)
        async def cancel_sleep():
            await asyncio.sleep(1)
            s.cancel()

        asyncio.create_task(cancel_sleep())
        try:
            print(await s)
        except asyncio.CancelledError as e:
            print('cancelled')

        # cancel streaming:
        u = stub.uppercase(request_stream=['aaa','bbb'])
        async def cancel_uppercase():
            await asyncio.sleep(2)
            u.cancel()

        asyncio.create_task(cancel_uppercase())
        try:
            async for word in u:
                print(word)
        except Exception as e:
            print(e)


asyncio.run(main())