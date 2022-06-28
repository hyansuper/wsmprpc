# see: https://docs.python.org/3/library/asyncio-stream.html
import asyncio
from wsmprpc.client import RPCClient
from tcp_socket_wrapper import tcp_socket_wrapper

async def main():
    async with tcp_socket_wrapper(*await asyncio.open_connection('localhost', 8000)) as socket:
        stub = RPCClient(socket)

        # normal rpc
        print(await stub.div(1, 3))

        # cancellation
        s = stub.sleep(3)
        async def cancel_sleep():
            await asyncio.sleep(1)
            s.cancel()
        try:
            asyncio.create_task(cancel_sleep())
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