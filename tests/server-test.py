from async4jsonrpc.server import JsonRpcServer

server = JsonRpcServer()
server.register_function(lambda x, y: x + y, 'add')
server.register_function(lambda x: x, 'ping')
server.serve('localhost', 8080)