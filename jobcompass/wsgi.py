"""Production WSGI entry point, served by a single threaded Gunicorn worker."""
import atexit
import os
import threading
from http import HTTPStatus

from .config import DB_PATH
from .public import PublicConfig
from .server import Application
from .web import WebGateway, MAX_BODY, response


class WSGIApplication:
    def __init__(self, app, public_config=None):
        self.gateway = WebGateway(app, int(os.environ.get('PORT', '8765')), public_config)

    def __call__(self, environ, start_response):
        headers = {key[5:].replace('_','-'):value for key,value in environ.items() if key.startswith('HTTP_')}
        method = environ.get('REQUEST_METHOD', 'GET')
        body = b''
        try:
            if method == 'POST':
                size = int(environ.get('CONTENT_LENGTH', '0') or '0')
                if not 0 < size <= MAX_BODY:
                    raise ValueError()
                body = environ['wsgi.input'].read(size)
                if len(body) != size:
                    raise ValueError()
            target = environ.get('PATH_INFO', '/')
            if environ.get('QUERY_STRING'):
                target += '?' + environ['QUERY_STRING']
            status, output_headers, data = self.gateway.handle(method, target, headers, body, environ.get('REMOTE_ADDR', ''))
        except (ValueError, UnicodeError):
            status, output_headers, data = response({'error':'请求大小或编码无效。'}, 400)
        start_response('{} {}'.format(status, HTTPStatus(status).phrase), output_headers)
        return [data]

    def close(self):
        self.gateway.close()


_application = None
_lock = threading.Lock()


def application(environ, start_response):
    global _application
    with _lock:
        if _application is None:
            if os.environ.get('JOBCOMPASS_PUBLIC') != '1':
                raise ValueError('生产 WSGI 入口必须启用 JOBCOMPASS_PUBLIC=1 并配置 HTTPS 域名；本机个人模式请运行 main.py。')
            config = PublicConfig.from_env()
            _application = WSGIApplication(Application(DB_PATH), config)
            atexit.register(_application.close)
    return _application(environ, start_response)
