import asyncio
import inspect
from collections import OrderedDict
from typing import Dict, Tuple, List, Optional, Union, Callable
import msgpack
from .rpc_stream import RPCStream
from . import msg_type as mtype
from .error import *

# import logging
# logger = logging.getLogger(__name__)


class RPCServer:

    def __init__(self, ws=None, *, timeout=10, use_list=False):
        self.ws = ws
        self.timeout = timeout
        self._packer = msgpack.Packer(use_bin_type=True)
        self._use_list = use_list
        self._tasks: Dict[int, Tuple[asyncio.Task, Optional[wsrpc.RPCStream]]] = {}
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
        return [(
            ('async ' if inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn) else '')+'def '+fname+str(inspect.signature(fn)), 
            fn.__doc__) 
            for fname, (fn, qsize) in self._rpc_fn.items()]

    async def run(self, ws=None):
        if ws is not None:
            self.ws = ws
        self._fn_list = list(self._rpc_fn.keys())
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
                    # try:
                    await self._on_msg(msg)
                    # except Exception as e:
                    #     logger.exception(e)

        finally:
            try: # cancel all tasks
                await asyncio.shield(self._join())
            except asyncio.CancelledError:
                await self._join()

    async def _join(self):
        remains = self._tasks.values()
        if remains:
            for t,q in remains:
                t.cancel()
            await asyncio.wait([t for t,q in self._tasks.values()], timeout=self.timeout)

    async def _on_msg(self, msg: object):
        msgtype, msgid = msg[:2]

        if msgtype == mtype.REQUEST or msgtype == mtype.NOTIFY:
            method_name, params = msg[2:]   
            if isinstance(method_name, int) and 0<=method_name<len(self._fn_list):
                method_name = self._fn_list[method_name]
            method, q_size = self._rpc_fn.get(method_name, (None, 0))
            if method_name and method:
                kwoa = inspect.getfullargspec(method).kwonlyargs
                if kwoa and kwoa[-1]=='request_stream':
                    q = RPCStream(q_size)
                else:
                    q = None

                if inspect.isasyncgenfunction(method):
                    task = asyncio.create_task(self._on_request_gen(msgid, method, params, q))

                elif inspect.iscoroutinefunction(method):
                    task = asyncio.create_task(self._on_request(msgid, method, params, q))

                else:
                    try:
                        ret = self._call(method, params, None)
                    except Exception as e:
                        await self._send_error(msgid, str(e))
                    else:
                        await self._send_response(msgid, ret)
                    return

                self._tasks[msgid] = task, q
                task.add_done_callback(lambda f: self._tasks.pop(msgid, None))

            else:
                await self._send_error(msgid, f'{method_name} method not found.')

        elif msgtype == mtype.REQUEST_STREAM_CHUNCK:
            self._tasks[msgid][1].force_put_nowait(msg[2])

        elif msgtype == mtype.REQUEST_STREAM_END:
            self._tasks[msgid][1].force_put_nowait(StopAsyncIteration())

        elif msgtype == mtype.REQUEST_CANCEL:
            t = self._tasks.get(msgid)
            t and t[0].cancel()

        else:
            raise RPCServerError("unknown msgtype")

    def _call(self, method, params, q):
        ptype = type(params)
        if ptype == list or ptype == tuple:
            return method(*params, request_stream=q) if q else method(*params)
        elif ptype == dict:
            return method(**params, request_stream=q) if q else method(**params)
        else:
            raise Exception('Wrong parameters for '+ method.__name__)

    async def _on_request(self, msgid: int, method: Callable, params: Union[list, dict], q: Optional[RPCStream]) -> None:
        try:
            ret = await self._call(method, params, q)
        except Exception as e:
            try:
                await self._send_error(msgid, str(e) or e.__class__.__name__)
            except ConnectionClosedOK:
                pass
        else:
            await self._send_response(msgid, ret)

    async def _on_request_gen(self, msgid: int, method: Callable, params: Union[list, dict], q: Optional[RPCStream]) -> None:
        try:
            async for resp in self._call(method, params, q):
                await self._send_stream_chunck(msgid, resp)
        except Exception as e:
            try:
                await self._send_error(msgid, str(e) or e.__class__.__name__)
            except ConnectionClosedOK:
                pass
        else:
            await self._send_stream_end(msgid)


    async def _send_response(self, msgid: int, result) -> None:
        await self.ws.send(self._packer.pack((mtype.RESPONSE, msgid, None, result)))

    async def _send_error(self, msgid: int, err: str) -> None:
        await self.ws.send(self._packer.pack((mtype.RESPONSE, msgid, err, None)))

    async def _send_stream_chunck(self, msgid: int, chunck) -> None:
        await self.ws.send(self._packer.pack((mtype.RESPONSE_STREAM_CHUNCK, msgid, chunck)))

    async def _send_stream_end(self, msgid: int) -> None:
        await self.ws.send(self._packer.pack((mtype.RESPONSE_STREAM_END, msgid)))
