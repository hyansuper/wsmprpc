class tcp_socket_wrapper:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
    async def __aiter__(self):
        while True:
            data = await self.reader.read(256)
            if data:
                yield data
            else:
                return
    async def send(self, data):
        self.writer.write(data)
        await self.writer.drain()
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args, **kwargs):
        self.writer.close()
        await self.writer.wait_closed()
