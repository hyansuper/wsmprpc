## thoughts on connection/streaming

### socket.io
#### pros:
* video/audio streaming and jsonrpc utilizing same connection on different events.

#### cons:
* event message overhead in every stream chunck, less efficient compared to pure websocket

### websocket
#### pros:
* no message overhead compared to socket.io
* easier to stream chucked data on web clients compared to http request

#### cons:
* jsonrpc and streaming takes different connections

### http streaming
#### pros:
* maybe the easiest to implement

#### cons:
* currently there's no way to stream chunked data to server from web client, although getting chunked data from server is possible using web stream api.

## Ref
* msgpack rpc spec(is this official/universial?): https://github.com/msgpack-rpc/msgpack-rpc/blob/master/spec.md
* json rpc spec: https://www.jsonrpc.org/specification
* asyncio: https://github.com/crazyguitar/pysheeet/blob/master/docs/notes/python-asyncio.rst
* `__await__`: https://mdk.fr/blog/python-coroutines-with-async-and-await.html