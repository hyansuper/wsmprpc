import asyncio
import inspect
from collections import OrderedDict
import msgpack
from .rpc_stream import RPCStream
from . import msg_type as mtype
from .error import *

class RPCServer:

    def __init__(self, ws=None, *, timeout=10, use_list=False):
        self.ws = ws
        self.timeout = timeout
        self._packer = msgpack.Packer(use_bin_type=True)
        self._use_list = use_list
        self._rpc_fn = OrderedDict()

    def register(self, fn=None, *, q_size=0):
        if fn:
            self._rpc_fn.update({fn.__name__: (fn, q_size)})
            return fn
        return lambda fn: self.register(fn, q_size=q_size)

    def unregister(self, fn):
        self._rpc_fn.pop(fn.__name__, None)
        return fn

    @property
    def rpc_doc(self):
        if not hasattr(self, '_rpc_doc'):
            self._rpc_doc = [
                (fname + str(inspect.signature(fn)), fn.__doc__ or '')
                for fname, (fn, qsize) in self._rpc_fn.items()]
            self._fn_list = list(self._rpc_fn.keys())
        return self._rpc_doc

    @staticmethod
    async def _join(tasks):
        remains = tasks.values()
        if remains:
            for t,q in remains:
                t.cancel()
            await asyncio.wait([t for t,q in tasks.values()], timeout=self.timeout)

    async def run(self, ws=None):
        if ws is not None:
            self.ws = ws
        tasks = {} # dict[msgid, (task, queue)]
        unpacker = msgpack.Unpacker(None, raw=False, use_list=self._use_list)
        try:
            await self.ws.send(self._packer.pack(self.rpc_doc))
            async for data in self.ws:
                unpacker.feed(data)
                while True:
                    try:
                        msg = unpacker.unpack()
                    except msgpack.exceptions.OutOfData:
                        break

                    msgtype, msgid = msg[:2]

                    if msgtype == mtype.REQUEST or msgtype == mtype.NOTIFY:
                        method_name = msg[2]
                        if isinstance(method_name, int) and 0<=method_name<len(self._fn_list):
                            method_name = self._fn_list[method_name]
                        method, q_size = self._rpc_fn.get(method_name, (None, 0))

                        if method_name and method:
                            kwoa = inspect.getfullargspec(method).kwonlyargs
                            task, q = None, None
                            if kwoa and kwoa[-1]=='request_stream':
                                q = RPCStream(q_size)

                            if inspect.isasyncgenfunction(method):
                                task = asyncio.create_task(self._on_request_gen(msgid, method, q, *msg[3:]))

                            elif inspect.iscoroutinefunction(method):
                                task = asyncio.create_task(self._on_request(msgid, method, q, *msg[3:]))

                            else:
                                try:
                                    ret = self._call(method, None, *msg[3:])
                                except Exception as e:
                                    await self._send_error(msgid, str(e))
                                else:
                                    await self._send_response(msgid, ret)

                            if task:
                                tasks[msgid] = task, q
                                task.add_done_callback(lambda f: tasks.pop(msgid, None))

                        else:
                            await self._send_error(msgid, f'{method_name} method not found.')

                    elif msgtype == mtype.REQUEST_STREAM_CHUNCK:
                        tasks[msgid][1].force_put_nowait(msg[2])

                    elif msgtype == mtype.REQUEST_STREAM_END:
                        tasks[msgid][1].force_close_nowait()

                    elif msgtype == mtype.REQUEST_CANCEL:
                        t = tasks.get(msgid)
                        t and t[0].cancel()

                    else:
                        raise RPCServerError("unknown msgtype")

        finally:
            try: # cancel all tasks
                await asyncio.shield(self._join(tasks))
            except asyncio.CancelledError:
                await self._join(tasks)


    def _call(self, method, q, args, kwargs=None):
        if kwargs is None:
            return method(*args, request_stream=q) if q else method(*args)
        else:
            return method(*args, **kwargs, request_stream=q) if q else method(*args, **kwargs)

    async def _on_request(self, msgid, method, q, args, kwargs=None):
        try:
            ret = await self._call(method, q, args, kwargs)
        except Exception as e:
            await self._send_error(msgid, str(e) or e.__class__.__name__)
        else:
            await self._send_response(msgid, ret)

    async def _on_request_gen(self, msgid, method, q, args, kwargs=None):
        try:
            async for resp in self._call(method, q, args, kwargs):
                await self._send_stream_chunck(msgid, resp)
        except Exception as e:
            await self._send_error(msgid, str(e) or e.__class__.__name__)
        else:
            await self._send_stream_end(msgid)


    async def _send_response(self, msgid, result):
        await self.ws.send(self._packer.pack((mtype.RESPONSE, msgid, None, result)))

    async def _send_error(self, msgid, err):
        await self.ws.send(self._packer.pack((mtype.RESPONSE, msgid, err, None)))

    async def _send_stream_chunck(self, msgid, chunck):
        await self.ws.send(self._packer.pack((mtype.RESPONSE_STREAM_CHUNCK, msgid, chunck)))

    async def _send_stream_end(self, msgid):
        await self.ws.send(self._packer.pack((mtype.RESPONSE_STREAM_END, msgid)))
