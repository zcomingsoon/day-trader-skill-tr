"""Run with python3 -m web.server. Bind localhost unless explicitly configured."""
import argparse
import json
import logging
import os
from pathlib import Path
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from .market import chart
from .store import Store

STATIC = Path(__file__).parent / 'static'


def make_server(host, port, db_path):
    store = Store(db_path)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, data, content_type='application/json; charset=utf-8'):
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if content_type.startswith('application/json') else data
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
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
            if urlparse(self.path).path != '/api/trades':
                return self.send(404, {'error':'Bulunamadı.'})
            if self.headers.get('X-Paper-Token') != token or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.send(403, {'error':'Geçersiz oturum.'})
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

    return ThreadingHTTPServer((host,port),Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8000')))
    parser.add_argument('--db',default=os.environ.get('PAPER_DB','.web-data/paper.sqlite3'))
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    server = make_server(args.host,args.port,args.db)
    print('Day Trader TR: http://%s:%s | Yalnızca sanal işlem' % (args.host,args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
