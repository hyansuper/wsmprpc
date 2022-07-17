import asyncio
import websockets
import wsmprpc
try:
    from collections import Iterable
except ImportError:
    from collections.abc import Iterable
from typing import AsyncGenerator

# Create a rpc server to register rpc functions to.
rpc_server = wsmprpc.RPCServer()

# Type hints and doc strings of rpc functions are very recommended, they will be sent to client

# **Normal rpc**
# Non-async rpc can't be cancelled
# Exceptions raised in rpc function will also raise on client side, e.g. divide by zero.
@rpc_server.register
def div(a:float, b:float) -> float:
    '''Return a divided by b.'''
    return a / b

# **Async rpc**
# Time-consuming rpc must be async
# It can be cancelled by client, use try block to do cleaning up if needed
@rpc_server.register
async def delay_echo(delay: float, echo: str) -> str:
    '''Return [echo] string after [delay] seconds.'''
    try:
        await asyncio.sleep(delay)
        return echo
    except asyncio.CancelledError:
        pass
    finally:
        pass # do cleaning up

# **Request-streaming rpc**
# The client sends a sequence of messages and the server returns one response msg.
# The function must take the an iterable or async-iterable keyword-only argument named 'request_stream' to get input chunks,
@rpc_server.register
async def sum(*, request_stream: Iterable[int]) -> int:
    '''Return Sum of all elements in input stream'''
    sum = 0
    async for i in request_stream:
        sum += i
    return sum

# **Response-streaming rpc**
# The client send one request msg and the server returns a sequence of messages.
# The function must be an async generator function that yields response chunks.
@rpc_server.register
async def repeat(word: str, count: int) -> AsyncGenerator[str, None]:
    '''Output [word] for [count] times'''
    while count > 0:
        count -= 1
        yield word

# **Combine request-streaming and response-streaming**
# You can also specify receive stream queue size, although not necessary
@rpc_server.register(q_size=10)
async def uppercase(*, request_stream: Iterable[str]) -> AsyncGenerator[str, None]:
    '''Convert input stream to uppercase'''
    async for word in request_stream:
        yield word.upper()

async def main():
    async with websockets.serve(rpc_server.run, "localhost", 8000):
        await asyncio.Future() # run forever, because future never calls set_result()

asyncio.run(main())
