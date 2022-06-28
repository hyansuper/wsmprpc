import asyncio
import functools
try:
    from collections import Iterable
except:
    from collections.abc import Iterable
import msgpack
from . import msg_type as mtype
from .rpc_stream import RPCStream
from .error import *

# import logging
# logger = logging.getLogger(__name__)

class RPCFuture(asyncio.Future):

    def __init__(self, msgid, start, cancel, q_size, response_stream):
        asyncio.Future.__init__(self)
        self._msgid = msgid
        self._start = start
        self._response_stream = response_stream
        self._q_size = q_size
        self._cancel = cancel
        self._request_sent = False

    @property
    def response_stream(self):
        if not self._response_stream:
            self._response_stream = RPCStream(self._q_size)
        return self._response_stream

    # not thread-safe
    def cancel(self):
        if not self.done() and self._request_sent:
            self._response_stream and self._response_stream.force_put_nowait(RPCClientError('Cancelled by client.'))
            self._cancel_task = asyncio.create_task(self._cancel(self._msgid))            
        return asyncio.Future.cancel(self)

    def __del__(self):
        self.cancel()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not (self.cancelled() or self._request_sent):
            self._request_sent = True
            await self._start()
        return await self.response_stream.__anext__()

    def __await__(self):
        if not (self.cancelled() or self._request_sent):
            self._request_sent = True
            yield from self._start().__await__()
        return (yield from asyncio.Future.__await__(self))


class RPCClient:
    def __init__(self, ws, *, use_list=False, use_fn_num=False):
        self.ws = ws
        self._use_list = use_list
        self._use_fn_num = use_fn_num
        self._packer = msgpack.Packer(use_bin_type=True)
        self._mid = 0
        self._tasks = {}
        self._doc_ls = None        
        self._fnames = None
        self._rpc_doc_fut = asyncio.Future()
        asyncio.create_task(self._run())

    @property
    def rpc_doc(self):
        return self._doc_ls

    def _next_msgid(self):
        if self._mid >= 2**20:
            self._mid = 0
        self._mid += 1
        return self._mid

    async def _run(self):
        unpacker = msgpack.Unpacker(None, raw=False, use_list=self._use_list)
        async for data in self.ws:
            # try:
            unpacker.feed(data)
            while True:
                try:
                    msg = unpacker.unpack()
                except msgpack.exceptions.OutOfData:
                    break

                if self._fnames is None:
                    self._doc_ls = msg
                    self._fnames = [sig[sig.find('def')+4: sig.index('(')] for sig, doc in self._doc_ls]
                    self._rpc_doc_fut.set_result(None)
                    continue
                msgtype, msgid = msg[:2]
                if msgtype == mtype.RESPONSE:
                    err, result = msg[2:]
                    t = self._tasks.pop(msgid, None)
                    if t and not t.done():
                        if err:
                            e = RPCServerError(err)
                            t.set_exception(e)
                            t._response_stream and t._response_stream.force_put_nowait(e)
                        else:
                            t.set_result(result)

                elif msgtype == mtype.RESPONSE_STREAM_CHUNCK:
                    self._tasks[msgid].response_stream.force_put_nowait(msg[2])

                elif msgtype == mtype.RESPONSE_STREAM_END:
                    t = self._tasks.pop(msgid, None)
                    if t and not t.done():
                        t.response_stream.force_put_nowait(StopAsyncIteration())
                        t.set_result(None)

                elif msgtype == mtype.RESPONSE_API:
                    self._rpc_doc_fut.set_result(msg[-1])

            # except Exception as e:
            #     logger.exception(str(e))
        


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

    async def _translate_method_name(self, method):
        if self._use_fn_num:
            if self._fnames is None:
                await self._rpc_doc_fut
            return self._fnames.index(method)
        return method

    def _request(self, method, *args, **kwargs):
        msgid = self._next_msgid()
        req_iter = kwargs.pop('request_stream', None)
        async def start():
            await self._send_request(msgid, await self._translate_method_name(method), args)
            if req_iter:
                await self._req_iter(msgid, req_iter)
        fut = RPCFuture(msgid=msgid, start=start, cancel=self._send_cancel, q_size=kwargs.pop('q_size', 0), response_stream=kwargs.pop('response_stream', None))
        self._tasks[msgid] = fut
        return fut
