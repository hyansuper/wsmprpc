import asyncio
import wsmprpc
from tcp_socket_wrapper import tcp_socket_wrapper

rpc_server = wsmprpc.RPCServer()

# for more rpc function examples, see: https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_server.py
@rpc_server.register
def div(a:float, b:float) -> float:
    '''divide a by b'''
    return a / b

async def handle_client(reader, writer):
    async with tcp_socket_wrapper(reader, writer) as socket:
        await rpc_server.run(socket)

async def main():
    # basic asyncio tcp server, see: https://docs.python.org/3/library/asyncio-stream.html#tcp-echo-server-using-streams
    server = await asyncio.start_server(handle_client, 'localhost', 8000)
    async with server:
        await server.serve_forever()

asyncio.run(main())
