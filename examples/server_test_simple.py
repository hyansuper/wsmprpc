import asyncio
import websockets
from wsmprpc import RPCServer

class SimpleHandler:

    # rpc method name cannot start with underscore
    def _private_method(self):
        pass

    # non-async rpc can't be cancelled
    def div(self, a, b):
        return a / b

    # long runing rpc must be async
    async def sleep(self, t):
        await asyncio.sleep(t)
        return 'done sleeping'

    # request-streaming rpc:
    # the client sends a sequence of messages and the server returns one response msg.
    # the function must take the last arg as a keyword argument named 'request_stream',
    # which is a sub class of asyncio.Queue.
    async def sum(self, *, request_stream):
        sum = 0
        async for a in request_stream:
            sum += a
        return sum

    # response-streaming rpc:
    # the client send one request msg and the server returns a sequence of messages.
    # the function must be an async generator function.
    async def repeat(self, word, count):
        while count > 0:
            count -= 1
            yield word

    # combine request-streaming and response-streaming
    async def uppercase(self, *, request_stream):
        async for word in request_stream:
            yield word.upper()



async def handle_ws(ws, path):
    await RPCServer(ws, SimpleHandler()).run()

ws_server = websockets.serve(handle_ws, "localhost", 8000)

asyncio.get_event_loop().run_until_complete(ws_server)
asyncio.get_event_loop().run_forever()