class tcp_socket_wrapper:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
    def __aiter__(self):
        return self
    async def __anext__(self):
        data = await self.reader.read(256)
        if data:
            return data
        else:
            raise StopAsyncIteration()
        # return b''
    async def send(self, data):
        self.writer.write(data)
        await self.writer.drain()
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        self.writer.close()
        await self.writer.wait_closed()