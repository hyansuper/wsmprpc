import asyncio

class RPCStream(asyncio.Queue):
    def __init__(self, maxsize=0):
        asyncio.Queue.__init__(self, maxsize)

    def __aiter__(self):
        return self

    async def __anext__(self):
        d = await self.get()
        if isinstance(d, Exception):
            raise d
        else:
            return d

    async def close(self):
        await self.put(StopAsyncIteration())

    def force_put_nowait(self, o):
        # if queue is full, then pop out an element to make room
        self.full() and self.get_nowait()
        self.put_nowait(o)
