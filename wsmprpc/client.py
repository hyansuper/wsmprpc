import asyncio
import logging
import functools
from collections import Iterable
from . import msg_type as mtype
import msgpack
from .rpc_stream import RPCStream
from .error import *

logger = logging.getLogger(__name__)

class RPCFuture(asyncio.Future):

    def __init__(self, msgid, start, cancel, q_size=0):
        asyncio.Future.__init__(self)
        self._start = start
        self._response_stream = None
        self._q_size = q_size
        self._cancel = cancel
        self._msgid = msgid
        self._iter_task = None
        self.add_done_callback(lambda f: self._iter_task and self._iter_task.cancel())

    @property
    def response_stream(self):
        if not self._response_stream:
            self._response_stream = RPCStream(self._q_size)
        return self._response_stream

    def cancel(self):
        if not self.cancelled():
            self._response_stream and self._response_stream.force_put_nowait(RPCError('Cancelled by client.'))
            asyncio.create_task(self._cancel(self._msgid))
        return asyncio.Future.cancel(self)

    def __aiter__(self):
        if not self._iter_task:
            self._iter_task = asyncio.create_task(self._start())
        return self.response_stream

    def __await__(self):
        # await self._coro
        # self._coro.__await__()
        if not self._iter_task:
            self._iter_task = asyncio.create_task(self._start())
        return asyncio.Future.__await__(self)


class RPCClient:
    def __init__(self, ws, *, use_list=False):
        self.ws = ws
        self._use_list = False
        self._packer = msgpack.Packer(use_bin_type=True)
        self._mid = 0
        self._tasks = {}
        asyncio.create_task(self._run())

    def _next_msgid(self):
        if self._mid >= 2**20:
            self._mid = 0
        self._mid += 1
        return self._mid

    async def _run(self):
        async for data in self.ws:
            try:
                msg = msgpack.unpackb(data, use_list=self._use_list)
                msgtype = msg[0]
                if msgtype == mtype.RESPONSE:
                    msgid, err, result = msg[1:]
                    t = self._tasks.pop(msgid, None)
                    if t:
                        if err:
                            if not t.cancelled():
                                e = RPCError(err)
                                t.set_exception(e)
                                t._response_stream and t._response_stream.force_put_nowait(e)
                        else:
                            t.set_result(result)

                elif msgtype == mtype.RESPONSE_STREAM_CHUNCK:
                    msgid, chunck = msg[1:]
                    self._tasks[msgid].response_stream.put_nowait(chunck)

                elif msgtype == mtype.RESPONSE_STREAM_END:
                    t = self._tasks.pop(msgid, None)
                    if t and not t.cancelled():
                        t.response_stream.force_put_nowait(StopAsyncIteration())
                        t.set_result(None)

            except Exception as e:
                logger.exception(str(e))


    def __getattr__(self, method):
        return functools.partial(self._request, method)

    async def _send_request(self, msgid, method, params):
        await self.ws.send(self._packer.pack((mtype.REQUEST, msgid, method, params)))

    async def _send_stream_chunck(self, msgid, chunck):
        await self.ws.send(self._packer.pack((mtype.REQUEST_STREAM_CHUNCK, msgid, chunck)))

    async def _send_stream_end(self, msgid):
        await self.ws.send(self._packer.pack((mtype.REQUEST_STREAM_END, msgid)))

    async def _send_cancel(self, msgid):
        await self.ws.send(self._packer.pack((mtype.REQUEST_CANCEL, msgid)))

    async def _req_iter(self, msgid, iter):
        if isinstance(iter, Iterable):
            for i in iter:
                await self._send_stream_chunck(msgid, i)
        else:
            async for i in iter:
                await self._send_stream_chunck(msgid, i)
        await self._send_stream_end(msgid)

    def _request(self, method, *args, **kwargs):
        msgid = self._next_msgid()
        req_iter = kwargs.pop('request_stream', None)
        async def start():
            await self._send_request(msgid, method, args or kwargs)
            if req_iter:
                asyncio.create_task(self._req_iter(msgid, req_iter))

        fut = RPCFuture(msgid=msgid, start=start, cancel=self._send_cancel)
        self._tasks[msgid] = fut
        return fut
