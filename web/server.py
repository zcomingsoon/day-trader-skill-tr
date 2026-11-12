"""Run with python3 -m web.server. Bind localhost unless explicitly configured."""
import argparse
import json
import logging
import os
from pathlib import Path
import hmac
from .auth import Auth
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from .market import chart
from .store import Store

STATIC = Path(__file__).parent / 'static'


def make_handler(db_path, password_hash=None, secure_cookie=True):
    auth = Auth(password_hash or os.environ.get('PAPER_PASSWORD_HASH'), secure_cookie)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    store = Store(db_path, os.environ.get('DATABASE_URL'))

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, data, content_type='application/json; charset=utf-8', cookie=None):
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if content_type.startswith('application/json') else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def params(self):
            return {k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}

        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == '/api/health':
                    return self.send(200, {'status':'ok','live_orders_enabled':False})
                if path in ('/login', '/login.js', '/style.css'):
                    name = {'/login':'login.html','/login.js':'login.js','/style.css':'style.css'}[path]
                    mime = 'text/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'text/html'
                    return self.send(200, (STATIC/name).read_bytes(), mime+'; charset=utf-8')
                token = auth.session(self.headers)
                if not token:
                    if path == '/':
                        self.send_response(303)
                        self.send_header('Location', '/login')
                        self.end_headers()
                        return
                    return self.send(401, {'error':'Giriş yapmanız gerekiyor.'})
                if path == '/api/session':
                    return self.send(200, {'token':token,'live_orders_enabled':False})
                if path == '/api/chart':
                    p = self.params()
                    return self.send(200, chart(p.get('symbol','THYAO'),p.get('market','BIST'),p.get('period','daily'),p.get('source','demo')))
                if path == '/api/portfolio':
                    p = self.params()
                    return self.send(200, store.snapshot(p.get('source','demo'),p.get('currency','TRY')))
                files = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
                if path not in files:
                    return self.send(404, {'error':'Bulunamadı.'})
                name = files[path]
                mime = {'html':'text/html','js':'text/javascript','css':'text/css'}[name.rsplit('.',1)[1]]
                return self.send(200, (STATIC/name).read_bytes(), mime+'; charset=utf-8')
            except ValueError as exc:
                self.send(400, {'error':str(exc)})
            except Exception:
                logging.exception('Veri isteği başarısız')
                self.send(502, {'error':'Veri alınamadı. Sağlayıcı bağlantısını kontrol edin; demo kaynağını ayrıca seçebilirsiniz.'})

        def do_POST(self):
            path = urlparse(self.path).path
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.send(403, {'error':'Geçersiz istek kaynağı.'})
            if path == '/api/login':
                # JSON content type prevents cross-origin form submissions; no CORS allowed.
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 4096 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                        raise ValueError()
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError()
                except (ValueError, TypeError):
                    return self.send(400, {'error':'Geçersiz giriş isteği.'})
                status, sid = auth.login(data.get('password'))
                return self.send(status, {'ok':True} if sid else {'error':'Giriş yapılamadı. Bilgilerinizi kontrol edin; çok sayıda denemeden sonra 5 dakika bekleyin.'}, cookie=auth.cookie(sid) if sid else None)
            token = auth.session(self.headers)
            if not token:
                return self.send(401, {'error':'Giriş yapmanız gerekiyor.'})
            if not hmac.compare_digest(self.headers.get('X-Paper-Token', ''), token):
                return self.send(403, {'error':'Geçersiz oturum.'})
            if path == '/api/logout':
                auth.logout(self.headers)
                return self.send(200, {'ok':True}, cookie=auth.cookie(expired=True))
            if path != '/api/trades':
                return self.send(404, {'error':'Bulunamadı.'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096:
                    raise ValueError('İstek boyutu geçersiz.')
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise ValueError('JSON gerekli.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict) or set(body) - {'symbol','market','source','side','qty','stop'}:
                    raise ValueError('Geçersiz işlem alanları; fiyat ve gerçek emir ayarı kabul edilmez.')
                quote = chart(body.get('symbol',''),body.get('market',''), 'intraday',body.get('source','demo'))
                result = store.trade(quote,body.get('side'),body.get('qty'),body.get('stop'))
                self.send(201,result)
            except (ValueError, TypeError) as exc:
                self.send(400, {'error':str(exc)})
            except Exception:
                logging.exception('Sanal işlem başarısız')
                self.send(502, {'error':'Sanal işlem tamamlanamadı. Veri kaynağını kontrol edin.'})

    return Handler

def make_server(host, port, db_path, password_hash=None, secure_cookie=True):
    return ThreadingHTTPServer((host,port), make_handler(db_path, password_hash, secure_cookie))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8000')))
    parser.add_argument('--db',default=os.environ.get('PAPER_DB','.web-data/paper.sqlite3'))
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    if os.environ.get('RENDER'):
        parser.error('Bulutta Gunicorn/WSGI başlangıcını kullanın; web/DEPLOYMENT.md dosyasını okuyun.')
    server = make_server(args.host,args.port,args.db, secure_cookie=os.environ.get('PAPER_LOCAL_HTTP') != '1')
    print('Day Trader TR: http://%s:%s | Yalnızca sanal işlem' % (args.host,args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
