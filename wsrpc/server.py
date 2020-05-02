import asyncio
import inspect
import logging
from typing import Dict, Tuple, List, Optional, Union, Callable
from .rpc_stream import RPCStream
from . import msg_type as mtype
from .error import *

import msgpack

logger = logging.getLogger(__name__)


class RPCServer:

    def __init__(self, ws, handler, *, timeout: int = 10, use_list = False):
        self.ws = ws
        self.timeout = timeout
        self._packer = msgpack.Packer(use_bin_type=True)
        self._use_list = use_list
        self._tasks: Dict[int, Tuple[asyncio.Task, Optional[wsrpc.RPCStream]]] = {}
        self.handler = handler

    async def run(self) -> None:
        async for data in self.ws:
            try:
                await self._on_data(data)
            except Exception as e:
                logger.exception(e)
        try:
            await asyncio.shield(self._join())
        except asyncio.CancelledError:
            await self._join()

    async def _join(self) -> None:
        for t,q in self._tasks.values():
            t.cancel()
        await asyncio.wait([t for t,q in self._tasks.values()], timeout=self.timeout)

    async def _on_data(self, data: bytes) -> None:
        msg = msgpack.unpackb(data, use_list=self._use_list)
        msgtype = msg[0]

        if msgtype == mtype.REQUEST or msgtype == mtype.NOTIFY:
            msgid, method_name, params = msg[1:]

            if method:= getattr(self.handler, method_name, None):
                kwoa = inspect.getfullargspec(method).kwonlyargs
                if kwoa and kwoa[-1]=='request_stream':
                    q_size = getattr(self.handler, 'q_size', {}).get(method_name, getattr(self.handler, 'default_q_size', 0))
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
            msgid, chunck = msg[1:]
            self._tasks[msgid][1].put_nowait(chunck)

        elif msgtype == mtype.REQUEST_STREAM_END:
            self._tasks[msg[1]][1].put_nowait(StopAsyncIteration())

        elif msgtype == mtype.REQUEST_CANCEL:
            msgid = msg[1]
            if t:= self._tasks.get(msgid):
                t[0].cancel()

        else:
            raise RPCError("unknown msgtype")

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
        except (asyncio.CancelledError, Exception) as e:
            await self._send_error(msgid, str(e) or e.__class__.__name__)
        else:
            await self._send_response(msgid, ret)

    async def _on_request_gen(self, msgid: int, method: Callable, params: Union[list, dict], q: Optional[RPCStream]) -> None:
        try:
            async for resp in self._call(method, params, q):
                await self._send_stream_chunck(msgid, resp)
        except (asyncio.CancelledError, Exception) as e:
            await self._send_error(msgid, str(e) or e.__class__.__name__)
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

