import asyncio

class RPCStream(asyncio.Queue):
    _stream_end = object()

    def __init__(self, maxsize=0):
        asyncio.Queue.__init__(self, maxsize)

    async def __aiter__(self):
        while True:
            d = await self.get()
            if d is self._stream_end:
                return
            elif isinstance(d, Exception):
                raise d
            else:
                yield d

    async def close(self):
        await self.put(self._stream_end)

    def force_close_nowait(self):
        self.force_put_nowait(self._stream_end)

    def force_put_nowait(self, o):
        # if queue is full, then pop out an element to make room
        self.full() and self.get_nowait()
        self.put_nowait(o)