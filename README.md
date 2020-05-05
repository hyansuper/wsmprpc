# Python msgpack RPC over websocket

One of the advantages of msgpack over json is that msgpack can carry binary data, that makes it very useful for streaming.

This demo project implements similar functions to that of google's gRPC, supporting not only one shot rpc, but also **bidirectional streaming** and **cancellation**, without the trouble to define .proto files, and it's asynchronous!

The examples use Sanic server to demonstrate different rpc functions.

### requirements:
python 3.8
