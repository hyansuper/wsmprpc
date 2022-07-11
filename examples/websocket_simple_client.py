import asyncio, websockets
import wsmprpc

async def main():
    async with websockets.connect('ws://localhost:8000') as ws, \
        wsmprpc.connect(ws) as stub:

        # show all RPCs
        print('rpc info:')
        for fun_sig, doc_str, request_stream, response_stream in stub.rpc_info:
            print(fun_sig)
            print(' '*4 + doc_str)
            print((request_stream, response_stream))
        print()

        # normal rpc
        print('1/3=', await stub.div(1, 3))

        # cancellation
        try:
            ech = stub.delay_echo(delay=2, echo='ok')
            asyncio.get_running_loop().call_later(1, ech.cancel)
            # or, await ech.async_cancel()
            print('echo=', await ech)
        except asyncio.CancelledError:
            print('echo is cancelled')

        # request-streaming
        print('sum of range(3)=', await stub.sum(request_stream=range(3)))

        # response-streaming
        print('repeat:', end=' ')
        async for i in stub.repeat('bla...', 4):
            print(i, end=' ')
        print()

        # combine request-streaming and response-streaming
        print('uppercase:', end=' ')
        async for i in stub.uppercase(request_stream=['hello', 'rpc']):
            print(i, end=' ')


asyncio.run(main())
