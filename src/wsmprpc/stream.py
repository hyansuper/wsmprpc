import asyncio

class RPCStream(asyncio.Queue):
    _stream_end = object()

    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        self._closed = False

    async def __aiter__(self):
        while (d:=await self.get()) is not self._stream_end:
            if isinstance(d, BaseException):
                raise d
            else:
                yield d

    @property
    def closed(self):
        return self._closed

    async def close(self):
        await self.put(self._stream_end)
        self._closed = True

    def force_close_nowait(self):
        self.force_put_nowait(self._stream_end)
        self._closed = True

    def force_put_nowait(self, o):
        # no error thrown even if queue is already closed
        if not self._closed:
            # if queue is full, then pop out an element to make room
            self.full() and self.get_nowait()
            self.put_nowait(o)
