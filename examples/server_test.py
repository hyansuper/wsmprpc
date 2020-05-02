import asyncio
from sanic import Sanic
import sys
sys.path.append('../')
from wsrpc import RPCServer

class SimpleHandler:

    # non-async rpc can't be cancelled
    def div(self, a, b):
        return a / b

    # long runing rpc must be async
    async def sleep(self, t):
        await asyncio.sleep(t)
        return 'done sleeping'

    # request stream rpc must take the last arg as a keyword argument named 'request_stream',
    # which is a sub class of asyncio.Queue.
    async def count(self, *, request_stream):
        sum = 0
        async for a in request_stream:
            await asyncio.sleep(1)
            sum += len(a)
        return sum

    # use `yield` to generate response stream, no return value is supported
    async def repeat(self, word, count):
        while count > 0:
            count -= 1
            yield word

    # combine request stream and response stream
    async def uppercase(self, *, request_stream):
        async for word in request_stream:
            yield word.upper()



app = Sanic(__name__)

@app.websocket("/")
async def home(request, ws):
    await RPCServer(ws, SimpleHandler()).run()


app.run(host="0.0.0.0", port=8000, auto_reload=True)
