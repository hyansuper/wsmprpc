# Get started

## Basic

* Server

Registering a function to be an RPC is simply done by using the `RPCServer.register` decorator

```python
import wsmprpc
rpc_server = wsmprpc.RPCServer()

rpc_server.register
def div(a:float, b:float) -> float:
	"""divide a by b"""
	return a / b
```

Also you can register async function, if it contains time-consuming operations.

Then you run the RPC server by integrating `RPCServer.run(ws)` method into any async web framework that supports websockets, e.g. [sanic](https://sanic.dev/), the `RPCServer.run(ws)` method take a websocket object as its parameter.
```python
import sanic
app = sanic.Sanic(__name__)

@app.websocket("/")
async def home(request, ws):
    await rpc_server.run(ws)

app.run(host="0.0.0.0", port=8000)
```

[server code](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_sanic_server.py)

* Client

On the client side, use `wsmprpc.connect(ws)` function in the `async with ...` statement to create a client handler, and use it to invoke any RPC.

```python
import asyncio
import websockets
import wsmprpc

async def main():
    async with websockets.connect('ws://localhost:8000') as ws, \
        wsmprpc.connect(ws) as client:

        response = await client.div(1, 3)
        print("1/3=", response)

asyncio.run(main())
```

As you can see, the RPC method defined on server side is readily available on the client side.

> **Note**
> Just remember that in the client's perspective, all RPC methods are async methods, even if they're non-async on the server side. So you should append `await` keyword to retrieve the response.

If you're not sure what RPCs are available or how to use them, `client.help()` or specifically `client.help('div')` will show you the RPC function signatures and docstrings written on the server side.

Exceptions raised in server RPC functions will also raise on the client side, try `await client.div(1, 0)` in the above example, a `division by zero` exception will be fired.

[client code](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_client.py)

## Cancellation

The client can cancel a running RPC execution on the server, but only if it's registered as an async function.
The server can catch `asyncio.CancelledError` exception and do cleaning up if needed.

* Server

The below server registers a RPC that delays a specified time before it echos the string sent by client

```python
@rpc_server.register
async def delay_echo(delay: float, echo: str) -> str
    '''Return [echo] string after [delay] seconds.'''
    try:
        await asyncio.sleep(delay)
        return echo
    except asyncio.CancelledError:
        pass
    finally:
        pass # do cleaning up
```

* Client

Now client invokes an `delay_echo` RPC that will delay 2 seconds before echo, but cancels the RPC in the 1st second.

```python
async def delay_cancel(delay, rpc):
    await asyncio.sleep(delay)
    rpc.cancel()

rpc = client.delay_echo(delay=2, echo="hello")

asyncio.create_task(delay_cancel(1, rpc))

try:
    print('echo:', await rpc)
except asyncio.CancelledError:
    print('rpc is cancelled')
```

## Request-streaming

A request-streaming RPC is the case where the client sends a sequence of data to server.

If the server registers an async function that takes a keyword-only argument named `request_stream`, then it can read a sequence of data sent by client from `request_stream`.

* Server

Here the server registers an RPC that will return the sum of the sequence of int's sent by client.

```python
@rpc_server.register
async def sum(*, request_stream: Iterable[int]) -> int:
    '''Return sum of all elements in input stream'''
    sum = 0
    async for i in request_stream:
        sum += i
    return sum
```

* Client

The client invokes the request-streaming RPC by passing an `Iterable` or `AsyncIterable` instance as the `request_stream` arguement.

```python
sum_of_1_to_3 = await client.sum(request_stream=range(1, 4))
print('sum of range(1, 4)=', sum_of_1_to_3)
```

Or, if you want to send the sequence of data dynamically, you can invoke the RPC first and later use the stream to send chunks of data one by one. Just remember to close the stream before you retrieve result from server.

```python
stream = wsmprpc.RPCStream()
rpc = asyncio.create_task(client.sum(request_stream=stream))

await stream.put(1)
await stream.put(2)
await stream.put(3)
await stream.close()

print('sum of [1,2,3]=', await rpc)
```

## Response-streaming

Response-streaming is when the server sends a sequence of data to client. The registered RPC function must be an async gererator function that yields chunks of data to be sent.

* Server

In the below the server registers an RPC that echos multiple times the string sent by client.

```python
@rpc_server.register
async def repeat(word: str, count: int) -> AsyncGenerator[str, None]:
    '''Output [word] for [count] times'''
    while count > 0:
        count -= 1
        yield word
```

* Client

```python
async for word in client.repeat('hello', 4):
    print(word)
```

## Combining request-streaming and response-streaming

If the server registers an async generator function that takes a keyword-only arguement named `request_stream`, it's a bi-directional streaming RPC.

* Server

```python
@rpc_server.register
async def uppercase(*, request_stream: Iterable[str]) -> AsyncGenerator[str, None]:
    '''Convert input stream to uppercase'''
    async for word in request_stream:
        yield word.upper()
```

* Client

```python
async for WORD in client.uppercase(request_stream=['hello', 'wsmprpc']):
    print(WORD)
```

## Misc

### Rename RPC function

```python
rpc_server.register(name=to_upper)
async def uppercase(...):
    ...
```

### Limit request-streaming queue size

```python
rpc_server.register(q_size=10)
async def sum(*, request_stream):
    ...
```
Earlier unprocessed data in the queue will be shifted out by new incoming data when the queue is full.
`q_size` is 0 by default, making the request_stream size limitless.

### More examples

https://github.com/hyansuper/wsmprpc/blob/master/examples/