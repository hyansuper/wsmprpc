# Python msgpack RPC over websocket

One of the advantage of msgpack over json is that msgpack can carry binary data, that makes it very useful for streaming.

This demo project implements similar functions of google's gRPC, supporting not only one shot rpc, but also *bidirectional streaming*, without the trouble to define .proto files, and it's asynchronous!

The examples uses Sanic server to demonstrate different rpc functions.
