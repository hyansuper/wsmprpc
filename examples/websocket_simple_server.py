import asyncio
import websockets
from wsmprpc.server import RPCServer

try:
    from collections import Iterable
except ImportError:
    from collections.abc import Iterable
from typing import AsyncGenerator

rpc_server = RPCServer()

# type hints and doc strings are very recommended, they will be sent to client

# non-async rpc can't be cancelled
@rpc_server.register
def div(a:float, b:float) -> float:
    '''doc here'''
    return a / b

# long runing rpc must be async
@rpc_server.register
async def sleep(t: float) -> str:
    '''sleep [t] seconds then return string'''
    await asyncio.sleep(t)
    return 'done sleeping'

# request-streaming rpc:
# the client sends a sequence of messages and the server returns one response msg.
# the function must take the last arg as a keyword argument named 'request_stream',
# which is a sub class of asyncio.Queue.
@rpc_server.register
async def sum(*, request_stream: Iterable[int]) -> int:
    '''sum all elements in input stream'''
    sum = 0
    async for a in request_stream:
        sum += a
    return sum

# response-streaming rpc:
# the client send one request msg and the server returns a sequence of messages.
# the function must be an async generator function.
@rpc_server.register
async def repeat(word: str, count: int) -> AsyncGenerator[str, None]:
    '''output [word] for [count] times'''
    while count > 0:
        count -= 1
        yield word

# combine request-streaming and response-streaming.
# you can also specify receive stream queue size, although not necessary
@rpc_server.register(q_size=10)
async def uppercase(*, request_stream: Iterable[str]) -> AsyncGenerator[str, None]:
    '''convert input stream to uppercase'''
    async for word in request_stream:
        yield word.upper()


async def main():
    async with websockets.serve(rpc_server.run, "localhost", 8000):
        await asyncio.Future() # run forever, because future never calls set_result()
        
asyncio.run(main())
