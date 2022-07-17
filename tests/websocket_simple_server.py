import asyncio
import websockets
import wsmprpc
try:
    from collections import Iterable
except ImportError:
    from collections.abc import Iterable
from typing import AsyncGenerator

rpc_server = wsmprpc.RPCServer()

@rpc_server.register
def div(a:float, b:float) -> float:
    '''Return a divided by b'''
    return a / b


@rpc_server.register
async def delay_echo(delay: float, echo: str) -> str:
    '''Return [echo] string after [delay] seconds.'''
    await asyncio.sleep(delay)
    return echo

@rpc_server.register
async def sum(*, request_stream: Iterable[int]) -> int:
    '''Return Sum of all elements in input stream'''
    sum = 0
    async for i in request_stream:
        sum += i
    return sum

@rpc_server.register
async def repeat(word: str, count: int, interval: float=.5) -> AsyncGenerator[str, None]:
    '''Output [word] for [count] times'''
    while count > 0:
        count -= 1
        yield word
        await asyncio.sleep(interval)

@rpc_server.register(q_size=10)
async def uppercase(*, request_stream: Iterable[str]) -> AsyncGenerator[str, None]:
    '''Convert input stream to uppercase'''
    async for word in request_stream:
        yield word.upper()
