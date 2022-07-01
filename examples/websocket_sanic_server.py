import asyncio
import sanic
from wsmprpc.server import RPCServer

rpc_server = RPCServer()

# non-async rpc can't be cancelled
@rpc_server.register
def div(a:float, b:float) -> float:
    return a / b

# long runing rpc must be async
@rpc_server.register
async def sleep(t):
    await asyncio.sleep(t)
    return 'done sleeping'

# request-streaming rpc:
# the client sends a sequence of messages and the server returns one response msg.
# the function must take the last arg as a keyword argument named 'request_stream',
# which is a sub class of asyncio.Queue.
@rpc_server.register
async def sum(*, request_stream):
    '''sum all elements in input stream'''
    sum = 0
    async for a in request_stream:
        sum += a
    return sum

# response-streaming rpc:
# the client send one request msg and the server returns a sequence of messages.
# the function must be an async generator function.
@rpc_server.register
async def repeat(word, count):
    '''output [word] for [count] times'''
    while count > 0:
        count -= 1
        yield word

# combine request-streaming and response-streaming.
# you can also specify stream queue size, although not necessary
@rpc_server.register(q_size=10)
async def uppercase(*, request_stream):
    '''convert input stream to uppercase'''
    async for word in request_stream:
        yield word.upper()


app = sanic.Sanic(__name__)

@app.websocket("/")
async def home(request, ws):
    await rpc_server.run(ws)

@app.route('/rpc_doc')
async def rpc_doc(request):
    return sanic.response.json(rpc_server.rpc_doc)

app.run(host="0.0.0.0", port=8000)
