[GitHub](https://github.com/shigebeyond/async4jsonrpc) | [Gitee](https://gitee.com/shigebeyond/async4jsonrpc)

# async4jsonrpc
This library is an asynchronous python library for the JSON-RPC specification.

It is licensed under the Apache License, Version 2.0
(http://www.apache.org/licenses/LICENSE-2.0.html).

## Installation
Install from PyPi via pip:

```sh
pip3 install async4jsonrpc
```

# Features

* Compliant with the JSON-RPC 2.0 specification
* High performance by asyncio
* Json serialization support via [jsonpickle](https://jsonpickle.github.io/)

## Usage
### Server Usage
[server-test.py](./tests/server-test.py)
```python
from async4jsonrpc.server import JsonRpcServer

# create RPC json server
server = JsonRpcServer()
# registers a function to respond to RPC requests.
server.register_function(lambda x, y: x + y, 'add')
server.register_function(lambda x: x, 'ping')
# start to serve RPC request
server.serve('localhost', 8080)
```

### Client Usage
[client-test.py](./tests/client-test.py)
```python
import asyncio
from async4jsonrpc.client import JsonRpcClient

# create RPC json client
client = JsonRpcClient('127.0.0.1', 8080)

async def call_rpc(i):
    # rpc: send rpc request
    r = await client.ping(f'hello {i}')
    print(r)

asyncio.run(call_rpc('shi'))
```

## Json serialize
I use [jsonpickle](https://jsonpickle.github.io/) library for serialization and deserialization of complex Python objects to and from JSON

1. Python object class example: 
[thing.py](./tests/thing.py)
```python
class Thing(object):
    def __init__(self, name):
        self.name = name
```

2. Client call rpc with a python object: 
[client-test.py](./tests/client-test.py)
```python
import asyncio
from async4jsonrpc.client import JsonRpcClient
from tests.thing import Thing

# create RPC json client
client = JsonRpcClient('127.0.0.1', 8080)

async def call_object_rpc():
    obj = Thing('Awesome')
    r = await client.ping(obj)
    print(r)

asyncio.run(call_object_rpc())
```