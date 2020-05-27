# wsmpRPC

Python msgpack RPC over websocket

## Features

One of the advantages of [msgpack](https://msgpack.org/) over json is that msgpack can carry binary data, that makes it very useful for streaming.

wsmpRPC implements similar functions to that of [gRPC](https://grpc.io/docs/tutorials/basic/python/), supporting not only one-shot RPC, but also **bidirectional streaming** and **cancellation**, without the trouble to define .proto files, and it's asynchronous!

## Install

`pip install wsmprpc`

## Examples

### server_test.py

```python
import asyncio
from sanic import Sanic
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


app = Sanic(__name__)

@app.websocket("/")
async def home(request, ws):
    await RPCServer(ws, SimpleHandler()).run()

app.run(host="0.0.0.0", port=8000)

```

### client_test.py

```python
import asyncio, websockets
from wsmprpc import RPCClient

async def main():
    async with websockets.connect('ws://localhost:8000') as ws:
        stub = RPCClient(ws)

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
        print(await stub.sum(request_stream=range(1, 3)))

        # get response-streaming
        async for i in stub.repeat('bla...', 4):
            print(i)

        # combine request-streaming and response-streaming
        async for i in stub.uppercase(request_stream=['hello', 'rpc']):
            print(i)


asyncio.run(main())
```