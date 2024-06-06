# 修改日志文件
from pyutilb.log import log
log.setFile("client.log")
import asyncio
import random
import threading
from asyncio import events, Future
from async4jsonrpc.comm import *
from typing import Union, Dict, Any

class JsonRpcClient:
    """
    rpc client，用于连接 server + 发送请求
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._conn = None # 连接
        self.futures: Dict[int, Future] = {} # 记录请求id对应的异步响应
        self._lock = asyncio.Lock()

    async def lazy_conn(self):
        '''
        延迟创建连接
            加锁保证线程安全
        '''
        if self._conn is None:
            async with self._lock:
                # 双重检查
                if self._conn is None:
                    reader, writer = await asyncio.open_connection(self.host, self.port)
                    self._conn = JsonRpcConn(reader, writer, self)  # 连接
        return self._conn

    def get_future(self, req_id: int):
        '''
        根据请求id，获得对应的异步响应
        '''
        return self.futures.get(req_id)

    def __getattr__(self, method_name):
        """
        返回代理调用rpc方法的函数
        """
        def _call(*args, **kwargs):
            return self.call(method_name, *args, **kwargs)

        return _call

    async def call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """
        代理rpc调用：内部实现是发送rpc请求，并等待响应
        :param method_name 方法名
        :param args 方法参数
        :param kwargs 方法参数
        :return 响应结果
        """
        if args and kwargs:
            raise Exception('Cannot make JSON-RPC call with both positional and keyword arguments')

        # 延迟创建连接
        conn = await self.lazy_conn()

        id = random.randint(1, 10 ** 6)
        while id in self.futures:
            id = random.randint(1, 10 ** 6)

        loop = events.get_running_loop()
        # 创建异步结果future
        future = self.futures[id] = loop.create_future()
        # 创建请求对象
        req = Request(
            method_name,
            params=args or kwargs or None,
            id=id)

        # 发送请求
        await conn.send_request(req)
        # 等待异步结果
        await future
        del self.futures[id]
        return future.result()

class JsonRpcConn(JSONHandler):
    '''
    rpc连接
    '''

    def __init__(self, reader: StreamReader, writer: StreamWriter, client: JsonRpcClient):
        super().__init__(reader, writer, False)
        self.client = client
        # 创建任务来接收并处理响应
        self.handle_responses_task = asyncio.create_task(self.handle_responses())

    async def handle_responses(self):
        '''
        死循环接收并处理响应
        '''
        while True:
            try:
                # 1 读响应
                resp = await asyncio.wait_for(self.read_json(), None)  # wait_for等待读取数据，第二个参数为等待时间(None表示无限等待)
                if not resp:
                    self.on_disconnected()
                    return # 中断死循环

                resp = Response.from_dict(resp)
                log.debug("%s handle response: %s", self.role, resp)

                # 2 处理响应
                self.on_response_received(resp)
            except ConnectionResetError as ex:
                await self.on_disconnected(ex)
                return  # 中断死循环
            except Exception as e:
                log.error('[Client] call rpc method error', exc_info=e)
                continue

    async def send_request(self, req: Request):
        '''
        发请求
        '''
        await self.write_json(req.json())
        await self.writer.drain()  # flush清空套接字

    def on_response_received(self, resp: Response) -> None:
        """
        处理收到的响应
        """
        future = self.client.get_future(resp.id)
        if future is None:
            raise Exception(f'Response {resp.id} not found')
        future.set_result(resp.get_or_raise())
