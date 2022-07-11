import asyncio
import sanic
import wsmprpc

rpc_server = wsmprpc.RPCServer()

# for more rpc function examples, see: https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_server.py
@rpc_server.register
def div(a:float, b:float) -> float:
    '''divide a by b'''
    return a / b


app = sanic.Sanic(__name__)

@app.websocket("/")
async def home(request, ws):
    await rpc_server.run(ws)

@app.route('/rpc_info')
async def rpc_doc(request):
    return sanic.response.json(rpc_server.rpc_info)

app.run(host="0.0.0.0", port=8000)
