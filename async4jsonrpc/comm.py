import asyncio
import inspect
import json
import jsonpickle
import threading
from asyncio import StreamWriter, StreamReader
from typing import Union, Callable, Any
from pyutilb.log import log

# json序列化
# 基础序列化, 不支持自定义类型
# dump_json = json.dumps
# load_json = json.loads
# 复杂序列化, 支持自定义类型
dump_json = jsonpickle.encode
load_json = jsonpickle.decode

def params_match_signature(method: Callable, params: Union[list, dict]) -> bool:
    '''
    检查是否符合方法签名
    '''
    if params == None or len(params) == 0:
        return True

    signature = inspect.signature(method)
    sig_params = signature.parameters.values()
    sig_param_kinds = [p.kind for p in sig_params]

    is_var_positional = inspect.Parameter.VAR_POSITIONAL in sig_param_kinds
    positional_count = len([p for p in sig_param_kinds if p in (
        inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)])

    is_var_keyword = inspect.Parameter.VAR_KEYWORD in sig_param_kinds
    keywords = [p.name for p in sig_params if p.kind in (
        inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]

    if type(params) == dict:
        return is_var_keyword or all(k in keywords for k in params.keys())
    else:
        return is_var_positional or len(params) <= positional_count

def call_with_params(method: Callable, params: Union[list, dict]) -> Any:
    '''
    调用方法
    '''
    if params == None:
        return method()

    if isinstance(params, dict):
        return method(**params)

    return method(*params)

class Request:
    """
    json rpc请求，包含方法名+参数+请求id
    """

    def __init__(self, method: str = None, params: Union[list, dict] = None, id: Union[int, str] = None):
        """
        构造函数
        :param method: 方法名
        :param params: 方法参数
        :param id: 请求id
        """
        if not method:
            raise Exception('Miss "method"')
        self.method = method
        self.params = params
        self.id = id

    @staticmethod
    def from_dict(dic: dict):
        """
        从字典中构建请求对象
        """
        method = dic.get('method')
        if not method:
            raise Exception('Miss "method" property')

        return Request(method, dic.get('params'), dic.get('id'))

    def json(self) -> str:
        return dump_json(self.__dict__)

    def __repr__(self):
        return f"Request({self.__dict__})"

class Response:
    """
    rpc响应
    """

    def __init__(self, result: Any = None, error: str = None, id: Union[int, str] = None):
        """
        构造函数
        :param result: rpc调用结果
        :param error: Exception of this Response. May be None. (default: None)
        :param id: ID of this Response.
        """
        if result and error:
            raise Exception('Response cannot be initialized with both result and exception values')
        self.result = result
        self.id = id
        self.error = error

    @staticmethod
    def from_dict(dic: dict):
        """
        从字典中构建响应对象
        """
        if not 'id' in dic:
            raise Exception('Miss "id" property')
        id = dic.get('id')

        return Response(result=dic.get('result'), error=dic.get('error'), id=id)

    def json(self) -> str:
        return dump_json(self.__dict__)

    def get_or_raise(self):
        '''
        获得结果值或抛出异常
        '''
        if (self.error is None):
            return self.result

        raise Exception(self.error)

    def __repr__(self):
        return f"Response({self.__dict__})"

class JSONHandler(object):
    '''
    json数据读写处理器
    '''

    def __init__(self, reader: StreamReader, writer: StreamWriter, is_server: bool):
        self.reader = reader
        self.writer = writer
        if is_server:
            self.role = '[Server]'
        else:
            self.role = '[Client]'
        self._lock = asyncio.Lock() # 写锁

    def write_int(self, v):
        '''
        写int
        '''
        # 写4字节
        bs = (v).to_bytes(4, byteorder="little", signed=False)
        self.writer.write(bs)

    async def read_int(self):
        '''
        读int
        '''
        # 读4字节
        bs = await self.reader.read(4)
        v = int.from_bytes(bs, byteorder='little', signed=False)
        return v

    async def write_json(self, v):
        '''
        写json
          先写字节长度，然后写字节
        '''
        async with self._lock:
            if not isinstance(v, str):
                v = dump_json(v)  # 先转json
            log.debug('%s write json: %s', self.role, v)
            bs = v.encode()
            n = len(bs)
            self.write_int(n) # 写字节长度
            self.writer.write(bs) # 写字节

    async def read_json(self):
        '''
        读json
          先读字节长度，然后读字节
        '''
        n = await self.read_int() # 读字节长度
        if n == 0:
            return None
        bs = await self.reader.read(n) # 读字节
        str = bs.decode()
        log.debug('%s read json: %s', self.role, str)
        return load_json(str)  # 转json

    async def on_disconnected(self, ex=None):
        '''
        连接关闭事件处理
          主动关闭writer
        '''
        log.error('%s disconnected', self.role, exc_info=ex)
        self.writer.close()  # 关闭套接字
        await self.writer.wait_closed()  # 等待套接字完全关闭