# wsmpRPC

asynchronous Python msgpack RPC over websocket (or TCP socket)

## Features

* **Asynchronous**
* Compared to json, [msgpack](https://msgpack.org/) supports **binary data**.
* Client is able to **cancel** long running calculation on server.
* Supports **bidirectional streaming** RPC, where the client sends/receives a sequence of messages to/from server within one RPC.
* No need to define .proto files like [gRPC](https://grpc.io/docs/tutorials/basic/python/). thanks to python's dynamic features, RPC methods defined on server side can be readily used by client as if they're client's own methods.
* **Exceptions** raised in server RPC methods will also raise on client side.
* Function signatures and docstrings written on server side are also known to client.
* Easy integration into any async web frameworks that support **websocket**.
* Support for **javascript** client on web browsers.

## Install

`pip install wsmprpc`

## Dependency:
* Python >= 3.8
* [msgpack-python](https://github.com/msgpack/msgpack-python)

## Getting started
[simple tutorial](https://github.com/hyansuper/wsmprpc/blob/master/get_started.md)

## Examples

Basic examples using **websocket**
* [websocket_simple_server.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_server.py)
* [websocket_simple_client.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_client.py)

Websocket with **sanic** server
* [websocket_sanic_server.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_sanic_server.py)

Infact, you can invoke RPC via **TCP** socket, or any other socket/stream as long as it has `async send(data)` method and supports `async for` iteration for receiving data.
* [tcp_server.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/tcp_server.py)
* [tcp_client.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/tcp_client.py)

**javascript** client example
* [client_test.html](https://github.com/hyansuper/wsmprpc/blob/master/js/client_test.html), 
requires [javascript versions of msgpack](https://github.com/ygoe/msgpack.js)