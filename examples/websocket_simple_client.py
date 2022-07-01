import asyncio, websockets
from wsmprpc.client import RPCClient

async def main():
    async with websockets.connect('ws://localhost:8000') as ws:
        stub = RPCClient(ws)

        # show available RPCs
        for fn, doc in await stub.get_rpc_doc():
            print(fn)
            print(' '*4 + doc)
        print()

        # normal rpc
        print(await stub.div(1, 3))

        # cancellation
        s = stub.sleep(3)
        async def cancel_sleep():
            await asyncio.sleep(1)
            s.cancel() # or better: await s.async_cancel()
        asyncio.create_task(cancel_sleep())
        try:
            print(await s)
        except asyncio.CancelledError as e:
            print('cancelled')

        # request-streaming
        print(await stub.sum(request_stream=[1,2,3]))

        # response-streaming
        async for i in stub.repeat('bla...', 4):
            print(i)

        # combine request-streaming and response-streaming
        async for i in stub.uppercase(request_stream=['hello', 'rpc']):
            print(i)


asyncio.run(main())
