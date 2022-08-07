import asyncio, websockets
import wsmprpc

async def main():
    async with websockets.connect('ws://localhost:8000') as ws, \
        wsmprpc.connect(ws) as stub:

        # print all rpc
        stub.help()

        # normal rpc
        print('1/3=', await stub.div(1, 3))

        # cancellation
        try:
            ech = stub.delay_echo(delay=2, echo='ok')
            ech.cancel() # or, await ech.async_cancel()
            print('delay_echo:', await ech)
        except asyncio.CancelledError:
            print('echo is cancelled')

        # request-streaming
        print('sum of range(3)=', await stub.sum(request_stream=range(3)))

        # response-streaming
        print('repeat:', ','.join([i async for i in stub.repeat('bla', 4)]))

        # combine request-streaming and response-streaming
        print('uppercase:', end=' ')
        async for i in stub.uppercase(request_stream=['hello', 'rpc']):
            print(i, end=' ')


asyncio.run(main())
