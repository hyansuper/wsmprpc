import asyncio
import functools
try:
    from collections import Iterable
except ImportError:
    from collections.abc import Iterable
import msgpack
from .msg_type import RPCMsgType
from .method_id_type import RPCMethodIDType
from .stream import RPCStream
from .error import *
from . import version

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
    def __init__(self, ws=None, *, pref_num_meth_id=False, use_single_float=False):
        self.ws = ws
        self._pref_num_meth_id = pref_num_meth_id
        self._packer = msgpack.Packer(use_bin_type=True, use_single_float=use_single_float)
        self._min_msgid = 1 # 0 reserved
        self._max_msgid = 2**16 -1
        self._msgid = self._min_msgid
        self._tasks = {}
        self._rpc_defs = None
        self._rpc_ls = None
        self._init_fut = asyncio.Future()

    async def connect(self, ws=None):
        if self.ws and ws:
            raise RPCClientError('Socket is already set')
        if self.ws is None:
            self.ws = ws
        asyncio.create_task(self._run())
        return await self._init_fut

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args, **kwargs):
        pass

    @property
    def rpc_defs(self):
        '''list of rpc methods (method_sigature, docstring, request_stream, response_stream)'''
        assert self._init_fut.done(), 'RPCClient not connected'
        return self._rpc_defs

    def help(self, method=None):
        '''print defintion of rpc [method], or print all rpc method defs if [method] is not provided'''
        if method is None:
            assert self._init_fut.done(), 'RPCClient not connected'
            for i in range(len(self._rpc_ls)):
                self.help(i)
                print('-'*10)
        else:
            method_index = self._meth_to_num(method) if isinstance(method, str) else method
            sig, docstr, request_stream, response_stream = self._rpc_defs[method_index]
            print(sig)
            print(' '*4, docstr)
            print(' '*4, f'[{request_stream=}, {response_stream=}]')

    def _next_msgid(self):
        msgid = self._msgid
        self._msgid += 1
        if self._msgid > self._max_msgid:
            self._msgid = self._min_msgid
        return msgid if msgid not in self._tasks else self._next_msgid()

    async def _run(self):
        unpacker = msgpack.Unpacker(None, raw=False, use_list=False)
        # send client verification
        await self.ws.send(self._packer.pack({'ver': version.__version__}))

        async for data in self.ws:
            unpacker.feed(data)
            for msg in unpacker:

                if not self._init_fut.done():
                    if (err:=msg.get('err')) is not None:
                        self._init_fut.set_exception(RPCServerError(str(err)))
                        return
                    self._max_msgid = msg.get('max_msgid', self._max_msgid)
                    self._msgid = self._min_msgid = msg.get('min_msgid', self._min_msgid)
                    assert self._min_msgid < self._max_msgid
                    self._rpc_defs = msg['rpc_defs']
                    self._use_num_meth_id = msg['mthid_t'] == RPCMethodIDType.NUM.value or \
                                        self._pref_num_meth_id and msg['mthid_t'] == RPCMethodIDType.STR_NUM.value
                    self._rpc_ls = [sig[:sig.index('(')] for sig, *_ in self._rpc_defs]
                    self._init_fut.set_result(msg)
                    continue

                msgtype, msgid = msg[:2]
                if msgtype == RPCMsgType.RESPONSE:
                    err, result = msg[2:]
                    t = self._tasks.pop(msgid, None)
                    if t and not t.done():
                        if err:
                            e = RPCServerError(str(err))
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

    def _meth_to_num(self, method):
        assert self._init_fut.done(), 'RPCClient not connected'
        try:
            return self._rpc_ls.index(method)
        except ValueError:
            raise RPCClientError(f"Unknown RPC method {method}")

    def _request(self, method, *args, **kwargs):
        method_index = self._meth_to_num(method)
        req, resp = self._rpc_defs[method_index][2:4]
        req_iter = kwargs.pop('request_stream', None)
        if req and req_iter is None:
            raise RPCClientError(f'{method} must take "request_stream" as a keyword arg.')
        elif not req and req_iter:
            raise RPCClientError(f'{method} is not a request-streaming RPC.')
        resp_iter = kwargs.pop('response_stream', RPCStream() if resp else None)
        msgid = self._next_msgid()
        async def start():
            await self._send_request(msgid, method_index if self._use_num_meth_id else method, args, kwargs)
            if req_iter:
                await self._req_iter(msgid, req_iter)
        fut = RPCFuture(msgid=msgid, start=start, cancel=self._send_cancel, response_stream=resp_iter)
        self._tasks[msgid] = fut
        return fut


def connect(ws):
    return RPCClient(ws)
