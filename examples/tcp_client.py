import asyncio
import wsmprpc
from tcp_socket_wrapper import tcp_socket_wrapper

async def main():
    # basic asyncio tcp connection, see: https://docs.python.org/3/library/asyncio-stream.html
    reader, writer = await asyncio.open_connection('localhost', 8000)

    async with tcp_socket_wrapper(reader, writer) as socket, \
        wsmprpc.connect(socket) as stub:

        print(await stub.div(1, 3))


asyncio.run(main())
