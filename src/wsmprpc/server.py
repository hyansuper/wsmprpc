import asyncio
import inspect
from collections import OrderedDict
import msgpack
from .stream import RPCStream
from .msg_type import RPCMsgType
from .method_id_type import RPCMethodIDType
from .error import *
from . import version

def _major_ver(ver):
    return ver.split('.')[0] if isinstance(ver, str) else None

class RPCServer:

    def __init__(self, ws=None):
        self.ws = ws
        self._packer = msgpack.Packer(use_bin_type=True)
        self._reg_rpc = OrderedDict() # {fname: (fn, qsize)}
        self._rpc_info = None # [(sig, docstr, req_stream, resp_stream)]
        self._rpc_ls = None # [fname]
        self._rpc_meth_id_type = RPCMethodIDType.STR_NUM
        self._done_reg = False

    def register(self, fn=None, *, q_size=0):
        assert not self._done_reg, 'Cannot register new RPC after server is started'
        if fn is None:
            return lambda fn: self.register(fn, q_size=q_size)
        assert inspect.isfunction(fn), f'{fn} is not a function'
        self._reg_rpc.update({fn.__name__: (fn, q_size)})
        return fn

    def unregister(self, fn):
        assert not self._done_reg, 'Cannot unregister RPC after server is started'
        self._reg_rpc.pop(fn.__name__, None)

    @property
    def rpc_info(self):
        '''(fn_sig, docstring, request_stream, response_stream)'''
        if self._rpc_info is None:
            self._rpc_info = [
                (fname + str(inspect.signature(fn)),
                    fn.__doc__ or '',
                    'request_stream' in inspect.getfullargspec(fn).kwonlyargs,
                    inspect.isasyncgenfunction(fn))
                for fname, (fn, qsize) in self._reg_rpc.items()]
            self._rpc_ls = list(self._reg_rpc.keys())
        return self._rpc_info

    @staticmethod
    async def _join(tasks, timeout=10):
        for t in tasks:
            t.cancel()
        await asyncio.wait(tasks, timeout=timeout)

    async def run(self, ws=None):
        if ws is not None:
            self.ws = ws
        self._done_reg = True
        tasks = {} # dict[msgid, (task, queue)]
        unpacker = msgpack.Unpacker(None, raw=False, use_list=False)
        verified = False
        try:
            async for data in self.ws:
                unpacker.feed(data)
                for msg in unpacker:

                    if not verified:
                        if _major_ver(msg.get('version')) == _major_ver(version.__version__):
                            await self.ws.send(self._packer.pack({'version': version.__version__,
                                                                'method_id_type': self._rpc_meth_id_type.value,
                                                                'rpc_info': self.rpc_info}))
                            verified = True
                            continue
                        else:
                            await self.ws.send(self._packer.pack({'error': f'Incompatible version, server: {version.__version__}'}))
                            return

                    msgtype, msgid = msg[:2]
                    if msgtype == RPCMsgType.REQUEST:
                        if msgid in self._tasks:
                            await self._send_error(msgid, f'Message id {msgid} already in use')
                            continue

                        method_name = msg[2]
                        if isinstance(method_name, int) and 0<=method_name<len(self._rpc_ls):
                            method_name = self._rpc_ls[method_name]
                        method, q_size = self._reg_rpc.get(method_name, (None, 0))

                        if method:
                            task, q = None, None
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
                            await self._send_error(msgid, f'Unknown method id {method_name}.')

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
