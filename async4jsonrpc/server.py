# 修改日志文件
from pyutilb.log import log
log.setFile("server.log")
import asyncio
import traceback
from typing import Dict
from async4jsonrpc.comm import *

class JsonRpcServer(object):
    '''
    json rpc 服务端
    '''

    def __init__(self):
        self.funcs: Dict[str, Callable] = {}

    def register_function(self, func=None, name=None):
        """
        注册单个rpc方法
        """
        if name is None:
            name = func.__name__
        self.funcs[name] = func
        return self

    def remove_function(self, func: Union[Callable, str]) -> None:
        '''
        删除单个方法
        '''
        name = func.__name__ if callable(func) else func
        if not name in self.funcs:
            raise Exception(f'Function "{name}" is not registered')
        del self.funcs[name]

    def get_function(self, name):
        '''
        获得单个rpc方法
        '''
        return self.funcs.get(name)

    async def handle_client_connected(self, reader: StreamReader, writer: StreamWriter):
        """
        处理client连接事件
            参数 reader/writer 由server自动传入
        """
        log.debug("[Server] client connected")
        await JsonRpcRequestHandler(reader, writer, self).handle_requests()

    def serve(self, host, port, blocking=True):
        '''
        启动server
        :param host
        :param port
        :param blocking 是否阻塞到loop结束
        '''
        async def main():
            # 启动服务器
            server = await asyncio.start_server(self.handle_client_connected, host=host, port=port)
            # 获取请求连接的客户端信息
            addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
            log.info(f'[Server] serving on %s', addrs)
            # 处理请求
            async with server:
                if blocking:
                    await server.serve_forever()
                else:
                    await server.start_serving()

        asyncio.run(main())

class JsonRpcRequestHandler(JSONHandler):
    '''
    json rpc请求处理器
    '''

    def __init__(self, reader: StreamReader, writer: StreamWriter, server: JsonRpcServer):
        super().__init__(reader, writer, True)
        self.server = server

    async def call_request_method(self, req: Request):
        '''
        调用请求对应的方法
        :param req
        :return 结果
        '''
        # 获得方法
        func = self.server.get_function(req.method)
        if func is None:
            raise Exception(f"No method: {req.method}")
        if not params_match_signature(func, req.params):
            raise Exception('Invalid params')
        # 调用方法
        if asyncio.iscoroutinefunction(func):
            result = await call_with_params(func, req.params)
        else:
            result = call_with_params(func, req.params)
        return result

    async def handle_requests(self):
        '''
        死循环一直处理client发过来的rpc请求
        '''
        while True:  # 循环接受数据，直到套接字关闭
            try:
                # 1 读请求
                req = await asyncio.wait_for(self.read_json(), None) # wait_for等待读取数据，第二个参数为等待时间(None表示无限等待)
                if not req:
                    await self.on_disconnected()
                    return # 中断死循环

                req = Request.from_dict(req)
                log.debug("%s handle request: %s", self.role, req)
                # 2 调用请求对应的方法
                ret = await self.call_request_method(req)
                # 3 封装成功的响应
                resp = Response(result=ret, id=req.id)
            except ConnectionResetError as ex:
                await self.on_disconnected(ex)
                return # 中断死循环
            except Exception as e:
                log.error('[Server] call request method error', exc_info=e)
                # 3 封装异常的响应
                err = f'Server error:{e}, trace:{traceback.format_exc()}'
                resp = Response(err=err, id=req.id)
            # 4 写响应
            self.write_json(resp.json())
            await self.writer.drain()  # flush清空套接字