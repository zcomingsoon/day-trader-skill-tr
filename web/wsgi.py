"""Production WSGI bridge sharing exactly the same authenticated route handlers."""
from email.message import Message
from io import BytesIO
import os
from urllib.parse import quote
from .server import make_handler


def create_app():
    if not os.environ.get('DATABASE_URL'):
        raise ValueError('Bulut yayını için DATABASE_URL gerekli; geçici disk kabul edilmez.')
    if os.environ.get('PAPER_LOCAL_HTTP') == '1':
        raise ValueError('Bulutta güvenli çerez zorunludur.')
    handler = make_handler(os.environ.get('PAPER_DB', '/tmp/paper-unused.sqlite3'))

    def app(environ, start_response):
        request = handler.__new__(handler)
        request.path = quote(environ.get('PATH_INFO', '/'), safe='/')
        if environ.get('QUERY_STRING'):
            request.path += '?' + environ['QUERY_STRING']
        request.headers = Message()
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                request.headers[key[5:].replace('_', '-')] = value
        for key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            if environ.get(key):
                request.headers[key.replace('_', '-')] = environ[key]
        request.rfile = environ['wsgi.input']
        request.wfile = BytesIO()
        response = {'status':'500 Internal Server Error', 'headers':[]}
        def send_response(code, message=None):
            response['status'] = str(code) + ' ' + request.responses.get(code, ('Unknown',))[0]
        request.send_response = send_response
        request.send_header = lambda key, value: response['headers'].append((key, value))
        request.end_headers = lambda: None
        method = environ.get('REQUEST_METHOD')
        if method == 'GET':
            request.do_GET()
        elif method == 'POST':
            request.do_POST()
        else:
            request.send(405, {'error':'Yöntem desteklenmiyor.'})
        start_response(response['status'], response['headers'])
        return [request.wfile.getvalue()]
    return app
