# wsmpRPC

asynchronous Python msgpack RPC over websocket(or TCP socket)

## Features

* **Asynchronous**
* Compared to json, [msgpack](https://msgpack.org/) supports **binary data**.
* Client is able to **cancel** long running calculation on server.
* Supports **bidirectional streaming** RPC, where the client sends/receives a sequence of messages to/from server within one RPC.
* No need to define .proto files like [gRPC](https://grpc.io/docs/tutorials/basic/python/). thanks to python's dynamic features, RPC functions defined on server side can be readily used by client as if they're client's own functions.
* Easy integration into any async web frameworks that support **websocket**.
* lib for **javascript** client on web browsers.

## Install

`pip install wsmprpc`

## Dependency:
[msgpack-python](https://github.com/msgpack/msgpack-python), and [javascript versions of msgpack](https://github.com/ygoe/msgpack.js) if js client is used.

## Examples

Following examples uses **websocket**
* [websocket_simple_server.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_server.py)
* [websocket_simple_client.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_client.py)
* [client_test.html (javascript client)](https://github.com/hyansuper/wsmprpc/blob/master/js/client_test.html)

Infact, you can invoke RPC via **TCP** socket, or any other socket/stream as long as it has `async send(data)` method and supports `async for` iteration for receiving data.
* [tcp_server.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/tcp_server.py)
* [tcp_client.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/tcp_client.py)