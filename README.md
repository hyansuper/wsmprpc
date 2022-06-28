# wsmpRPC

Python msgpack RPC over websocket

## Features

* **Asynchronous**
* Compared to json, [msgpack](https://msgpack.org/) supports **binary data**.
* Client is able to **cancel** long running calculation on server.
* Supports **bidirectional streaming** RPC, where the client sends/receives a sequence of messages to/from server within one RPC, similar to [gRPC](https://grpc.io/docs/tutorials/basic/python/).
* No need to define .proto files, thanks to python's dynamic features, RPC methods defined on server side can be readily used by client as if it's client's own method.
* Easy integration into any async web frameworks that support **websocket**.
* lib for **javascript** client on web browsers.

## Install

`pip install wsmprpc`

## Dependency:
[python](https://msgpack.org/) and [javascript](https://github.com/ygoe/msgpack.js) versions of msgpack 

## Examples
* [websocket_simple_server.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_server.py)
* [websocket_simple_client.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/websocket_simple_client.py)
* [client_test.html (javascript client)](https://github.com/hyansuper/wsmprpc/blob/master/js/client_test.html)

Inface, you can transmit RPC via TCP socket, or any other socket as long as it has `async send(data)` method and supports `async for` iteration for receiving data.
* [tcp_server.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/tcp_server.py)
* [tcp_client.py](https://github.com/hyansuper/wsmprpc/blob/master/examples/tcp_client.py)