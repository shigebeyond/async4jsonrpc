import asyncio
import time
from pyutilb.log import log
log.setLevel('info')
from pyutilb import EventLoopThreadPool
from async4jsonrpc.client import JsonRpcClient
from tests.thing import Thing

client = JsonRpcClient('127.0.0.1', 8080)

async def call_rpc(i):
    r = await client.ping(f'hello {i}')
    print(f"call_rpc ( {i} ) = {r}")

# 简单单次调用
def simple_call():
    asyncio.run(call_rpc('shi'))

# 多线程并发调用
def multi_threads_call():
    pool = EventLoopThreadPool(10)
    for i in range(0, 1000):
        pool.exec(call_rpc(i))
        # pool.exec(test, i)
    time.sleep(6)
    print("over")
    pool.shutdown()

# 复杂对象的调用
async def call_object_rpc():
    obj = Thing('Awesome')
    r = await client.ping(obj)
    print(r)

def object_call():
    asyncio.run(call_object_rpc())

if __name__ == '__main__':
    # simple_call()
    multi_threads_call()
    # object_call()