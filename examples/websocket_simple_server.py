import asyncio
import websockets
import wsmprpc
from typing import AsyncGenerator, Iterable, AsyncIterable

# Create a rpc server to register rpc functions to.
rpc_server = wsmprpc.RPCServer()


# Normal rpc
@rpc_server.register
def div(a:float, b:float) -> float:
    '''Return a divided by b.'''
    return a / b

# Async rpc
@rpc_server.register
async def delay_echo(delay: float, echo: str) -> str:
    '''Return [echo] string after [delay] seconds.'''
    try:
        await asyncio.sleep(delay)
        return echo
    except asyncio.CancelledError:
        pass # when the client cancels server execution
    finally:
        pass # do cleaning up

# Request-streaming rpc
@rpc_server.register
async def sum(*, request_stream: Iterable[int]) -> int:
    '''Return sum of all elements in input stream'''
    sum = 0
    async for i in request_stream:
        sum += i
    return sum

# Response-streaming rpc
@rpc_server.register
async def repeat(word: str, count: int) -> AsyncGenerator[str, None]:
    '''Output [word] for [count] times'''
    while count > 0:
        count -= 1
        yield word

# Combine request-streaming and response-streaming
@rpc_server.register
async def uppercase(*, request_stream: Iterable[str]) -> AsyncGenerator[str, None]:
    '''Convert input stream to uppercase'''
    async for word in request_stream:
        yield word.upper()

async def main():
    async with websockets.serve(rpc_server.run, "localhost", 8000):
        await asyncio.Future() # run forever, because future never calls set_result()

asyncio.run(main())
