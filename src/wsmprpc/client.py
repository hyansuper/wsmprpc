import asyncio
import functools
try:
    from collections import Iterable
except ImportError:
    from collections.abc import Iterable
import msgpack
from .msg_type import RPCMsgType
from .method_type import RPCMethodType
from .stream import RPCStream
from .error import *

class RPCFuture(asyncio.Future):

    def __init__(self, msgid, start, cancel, *, response_stream):
        super().__init__()
        self._msgid = msgid
        self._start = start
        self._response_stream = response_stream
        self._cancel = cancel
        self._request_sent = False

    @property
    def response_stream(self):
        if self._response_stream is None:
            raise RPCClientError('Not a response-streaming rpc')
        return self._response_stream

    def cancel(self):
        '''
        `cancel()` immediately returns False if the RPC is already done or cancelled.
        Otherwise immediately returns True and will shedule a task to send cancel command to server.
        This method behaves consistently with asyncio.Future.cancel(), but usually `async_cancel()` is preferred.
        '''
        if not self.done() and self._request_sent:
            self._response_stream and self._response_stream.force_put_nowait(asyncio.CancelledError())
            self._cancel_task = asyncio.create_task(self._cancel(self._msgid))
        return super().cancel()

    async def async_cancel(self):
        '''
        Same as `cancel()` except that `async_cancel()` awaits the cancel command be sent to server,
        but no guarantee how to server will react.
        '''
        if not self.done() and self._request_sent:
            ret = super().cancel()
            self._response_stream and self._response_stream.force_put_nowait(asyncio.CancelledError())
            await self._cancel(self._msgid)
            return ret
        return super().cancel()

    # def __del__(self):
    #     self.cancel()

    async def __aiter__(self):
        if self._response_stream is None:
            raise RPCClientError('Not a response-streaming rpc')
        if self.cancelled():
            raise asyncio.CancelledError
        elif not self._request_sent:
            self._request_sent = True
            await self._start()
        async for x in self._response_stream:
            yield x

    def __await__(self):
        if not (self.cancelled() or self._request_sent):
            self._request_sent = True
            yield from self._start().__await__()
        return (yield from super().__await__())


class RPCClient:
    def __init__(self, ws=None, *, meth_num_first=False):
        self.ws = ws
        self._meth_num_first = meth_num_first
        self._packer = msgpack.Packer(use_bin_type=True)
        self._mid = 1 # 0 reserved
        self._tasks = {}
        self._rpc_info = None
        self._rpc_ls = None
        self._rpc_meth_type = None
        self._init_fut = asyncio.Future()

    async def connect(self, ws=None):
        if self.ws and ws:
            raise RPCClientError('Socket is already set')
        if self.ws is None:
            self.ws = ws
        asyncio.create_task(self._run())
        await self._init_fut

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args, **kwargs):
        pass

    @property
    def rpc_info(self):
        '''(method_sigature, docstring, request_stream, response_stream)'''
        assert self._init_fut.done()
        return self._rpc_info

    @property
    def rpc_method_type(self):
        assert self._init_fut.done()
        return self._rpc_meth_type

    def _next_msgid(self):
        if self._mid >= 2**20:
            self._mid = 1
        self._mid += 1
        return self._mid

    async def _run(self):
        unpacker = msgpack.Unpacker(None, raw=False, use_list=False)
        async for data in self.ws:
            unpacker.feed(data)
            for msg in unpacker:

                if not self._init_fut.done():
                    self._rpc_meth_type, self._rpc_info = msg
                    self._use_meth_num = self._rpc_meth_type == RPCMethodType.NUM.value or \
                                        self._meth_num_first and self._rpc_meth_type == RPCMethodType.STR_NUM.value
                    self._rpc_ls = [sig[:sig.index('(')] for sig, *_ in self._rpc_info]
                    self._init_fut.set_result(None)
                    continue

                msgtype, msgid = msg[:2]
                if msgtype == RPCMsgType.RESPONSE:
                    err, result = msg[2:]
                    t = self._tasks.pop(msgid, None)
                    if t and not t.done():
                        if err:
                            e = RPCServerError(err)
                            t.set_exception(e)
                            t._response_stream and t._response_stream.force_put_nowait(e)
                        else:
                            t.set_result(result)

                elif msgtype == RPCMsgType.RESPONSE_STREAM_CHUNCK:
                    self._tasks[msgid].response_stream.force_put_nowait(msg[2])

                elif msgtype == RPCMsgType.RESPONSE_STREAM_END:
                    t = self._tasks.pop(msgid, None)
                    if t and not t.done():
                        t.response_stream.force_close_nowait()
                        t.set_result(None)
        


    def __getattr__(self, method):
        return functools.partial(self._request, method)

    async def _send_request(self, msgid, method, args, kwargs):
        pk = (RPCMsgType.REQUEST.value, msgid, method, args, kwargs) if kwargs else (RPCMsgType.REQUEST.value, msgid, method, args)
        await self.ws.send(self._packer.pack(pk))

    async def _send_stream_chunck(self, msgid, chunck):
        await self.ws.send(self._packer.pack((RPCMsgType.REQUEST_STREAM_CHUNCK.value, msgid, chunck)))

    async def _send_stream_end(self, msgid):
        await self.ws.send(self._packer.pack((RPCMsgType.REQUEST_STREAM_END.value, msgid)))

    async def _send_cancel(self, msgid):
        await self.ws.send(self._packer.pack((RPCMsgType.REQUEST_CANCEL.value, msgid)))

    async def _req_iter(self, msgid, iter):
        if isinstance(iter, Iterable):
            for i in iter:
                await self._send_stream_chunck(msgid, i)
        else:
            async for i in iter:
                await self._send_stream_chunck(msgid, i)
        await self._send_stream_end(msgid)

    def _request(self, method, *args, **kwargs):
        try:
            method_index = self._rpc_ls.index(method)
        except ValueError:
            raise RPCClientError(f"Unknown RPC method {method}")
        req, resp = self._rpc_info[method_index][2:4]
        req_iter = kwargs.pop('request_stream', None)
        if req and req_iter is None:
            raise RPCClientError(f'{method} must take "request_stream" as a keyword arg.')
        elif not req and req_iter:
            raise RPCClientError(f'{method} is not a request-streaming RPC.')
        resp_iter = kwargs.pop('response_stream', RPCStream() if resp else None)
        msgid = self._next_msgid()
        async def start():
            await self._send_request(msgid, method_index if self._use_meth_num else method, args, kwargs)
            if req_iter:
                await self._req_iter(msgid, req_iter)
        fut = RPCFuture(msgid=msgid, start=start, cancel=self._send_cancel, response_stream=resp_iter)
        self._tasks[msgid] = fut
        return fut


def connect(ws):
    return RPCClient(ws)
