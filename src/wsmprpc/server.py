import asyncio
import inspect
from collections import OrderedDict
import msgpack
from .stream import RPCStream
from .msg_type import RPCMsgType
from .error import *

class RPCServer:

    def __init__(self, ws=None, *, use_list=False):
        self.ws = ws
        self._packer = msgpack.Packer(use_bin_type=True)
        self._use_list = use_list
        self._rpc_info = None # [(sig, docstr, req_stream, resp_stream)]
        self._rpc_ls = None # [fname]
        self._rpc_fn = OrderedDict() # {fname: (fn, qsize)}

    def register(self, fn=None, *, q_size=0):
        if fn:
            self._rpc_fn.update({fn.__name__: (fn, q_size)})
            return fn
        return lambda fn: self.register(fn, q_size=q_size)

    def unregister(self, fn):
        self._rpc_fn.pop(fn.__name__, None)

    @property
    def rpc_info(self):
        '''(fn_sig, docstring, request_stream, response_stream)'''
        if self._rpc_info is None:
            self._rpc_info = [
                (fname + str(inspect.signature(fn)),
                    fn.__doc__ or '',
                    'request_stream' in inspect.getfullargspec(fn).kwonlyargs,
                    inspect.isasyncgenfunction(fn))
                for fname, (fn, qsize) in self._rpc_fn.items()]
            self._rpc_ls = list(self._rpc_fn.keys())
        return self._rpc_info

    @staticmethod
    async def _join(tasks, timeout=10):
        for t in tasks:
            t.cancel()
        await asyncio.wait(tasks, timeout=timeout)

    async def run(self, ws=None):
        if ws is not None:
            self.ws = ws
        tasks = {} # dict[msgid, (task, queue)]
        unpacker = msgpack.Unpacker(None, raw=False, use_list=self._use_list)
        try:
            await self.ws.send(self._packer.pack(self.rpc_info))
            async for data in self.ws:
                unpacker.feed(data)
                for msg in unpacker:

                    msgtype, msgid = msg[:2]
                    if msgtype == RPCMsgType.REQUEST:
                        method_name = msg[2]
                        if isinstance(method_name, int) and 0<=method_name<len(self._fn_list):
                            method_name = self._fn_list[method_name]
                        method, q_size = self._rpc_fn.get(method_name, (None, 0))

                        if method_name and method:
                            task, q = None, None
                            # kwoa = inspect.getfullargspec(method).kwonlyargs
                            # if kwoa and kwoa[-1]=='request_stream':
                            if 'request_stream' in inspect.getfullargspec(method).kwonlyargs:
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
                            await self._send_error(msgid, f'Unknown function {method_name}.')

                    else:
                        task, q = tasks.get(msgid, (None, None))
                        # if t is None:
                            # await self._send_error(msgid, f'Wrong message id {msgid}.')

                        if msgtype == RPCMsgType.REQUEST_STREAM_CHUNCK:
                            q and q.force_put_nowait(msg[2])

                        elif msgtype == RPCMsgType.REQUEST_STREAM_END:
                            q and q.force_close_nowait()

                        elif msgtype == RPCMsgType.REQUEST_CANCEL:
                            task and task.cancel()

                        else:
                            await self._send_error(msgid, f'Wrong message type {msgtype}.')

        finally: # cancel remaining tasks
            tasks and await asyncio.shield(self._join(list(t for t, q in tasks.values())))


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
        await self.ws.send(self._packer.pack((RPCMsgType.RESPONSE.value, msgid, None, result)))

    async def _send_error(self, msgid, err):
        await self.ws.send(self._packer.pack((RPCMsgType.RESPONSE.value, msgid, err, None)))

    async def _send_stream_chunck(self, msgid, chunck):
        await self.ws.send(self._packer.pack((RPCMsgType.RESPONSE_STREAM_CHUNCK.value, msgid, chunck)))

    async def _send_stream_end(self, msgid):
        await self.ws.send(self._packer.pack((RPCMsgType.RESPONSE_STREAM_END.value, msgid)))
