import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web.auth import Auth, password_hash
from web.server import make_server
from web.store import Store

PASSWORD = 'test-only-password-123456'

class Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded = password_hash(PASSWORD)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name)/'paper.sqlite3')
        self.server = make_server('127.0.0.1', 0, self.db, self.encoded, False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, data=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        h = {'Content-Type':'application/json'}
        h.update(headers or {})
        conn.request('POST' if data is not None else 'GET', path, json.dumps(data) if data is not None else None, h)
        r = conn.getresponse()
        result = r.status, dict(r.getheaders()), r.read()
        conn.close()
        return result

    def login(self):
        status, headers, _ = self.request('/api/login', {'password':PASSWORD})
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        return {'Cookie':headers['Set-Cookie'].split(';')[0]}

    def test_private_routes_and_missing_configuration(self):
        for route in ['/api/session','/api/portfolio','/api/chart','/app.js']:
            self.assertEqual(self.request(route)[0], 401)
        self.assertEqual(self.request('/')[0], 303)
        self.assertEqual(self.request('/login')[0], 200)
        with self.assertRaises(ValueError):
            Auth(None)

    def test_login_trade_persistence_csrf_and_logout(self):
        headers = self.login()
        status, _, body = self.request('/api/session', headers=headers)
        self.assertEqual(status, 200)
        token = json.loads(body)['token']
        trade = dict(symbol='THYAO',market='BIST',source='demo',side='buy',qty=1,stop=1)
        self.assertEqual(self.request('/api/trades',trade,headers)[0],403)
        headers['X-Paper-Token'] = token
        self.assertEqual(self.request('/api/trades',trade,{**headers,'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(self.request('/api/trades',trade,headers)[0],201)
        snapshot = Store(self.db).snapshot('demo','TRY')
        self.assertEqual(len(snapshot['trades']),1)
        self.assertEqual(len(Store(self.db).snapshot('demo','TRY')['positions']),1)
        self.assertEqual(self.request('/api/logout',{},headers)[0],200)
        self.assertEqual(self.request('/api/portfolio',headers=headers)[0],401)

    def test_chart_includes_free_analysis(self):
        headers = self.login()
        status, _, body = self.request('/api/chart?symbol=THYAO&market=BIST&source=demo', headers=headers)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result['analysis']['method'], 'rules')
        self.assertIn('DEMO', result['data_notice'])
        self.assertFalse(result['live_orders_enabled'])

    def test_bad_password_limit_and_malformed_login(self):
        self.assertEqual(self.request('/api/login',[])[0],400)
        for _ in range(5):
            self.assertEqual(self.request('/api/login',{'password':'wrong'})[0],401)
        self.assertEqual(self.request('/api/login',{'password':PASSWORD})[0],429)

    def test_sessions_expire_secure_cookies_and_isolated_csrf(self):
        auth = Auth(self.encoded)
        self.assertIn('Secure',auth.cookie('test'))
        _, sid = auth.login(PASSWORD)
        headers = {'Cookie':'paper_session='+sid}
        self.assertTrue(auth.session(headers))
        auth.sessions[sid] = (0, 'expired')
        self.assertIsNone(auth.session(headers))
        a, b = self.login(), self.login()
        token = json.loads(self.request('/api/session',headers=a)[2])['token']
        self.assertEqual(self.request('/api/logout',{}, {**b,'X-Paper-Token':token})[0],403)


class WSGI(unittest.TestCase):
    def test_production_bridge_uses_same_auth_and_requires_remote_database(self):
        from io import BytesIO
        from unittest.mock import patch
        from web.wsgi import create_app
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError):
                create_app()
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp)/'test.sqlite3')
            # Exercise WSGI routing on real SQLite; live PostgreSQL is a separate acceptance check.
            with patch.dict('os.environ', {'DATABASE_URL':'test-only', 'PAPER_PASSWORD_HASH':password_hash(PASSWORD), 'PAPER_DB':db}, clear=True):
                with patch('web.server.Store', side_effect=lambda path, url: Store(path)):
                    app = create_app()
            def request(path, data=None, cookie=None):
                environ = {'PATH_INFO':path,'REQUEST_METHOD':'GET' if data is None else 'POST','wsgi.input':BytesIO()}
                if data is not None:
                    body = json.dumps(data).encode()
                    environ.update({'wsgi.input':BytesIO(body),'CONTENT_LENGTH':str(len(body)),'CONTENT_TYPE':'application/json'})
                if cookie:
                    environ['HTTP_COOKIE'] = cookie
                response = {}
                def start(status, headers):
                    response.update(status=status,headers=dict(headers))
                response['body'] = b''.join(app(environ,start))
                return response
            self.assertTrue(request('/api/portfolio')['status'].startswith('401'))
            login = request('/api/login',{'password':PASSWORD})
            self.assertTrue(login['status'].startswith('200'))
            self.assertIn('Secure',login['headers']['Set-Cookie'])
            cookie = login['headers']['Set-Cookie'].split(';')[0]
            self.assertTrue(request('/api/portfolio',cookie=cookie)['status'].startswith('200'))
            self.assertTrue(request('/',cookie=cookie)['status'].startswith('200'))

class PostgresSQL(unittest.TestCase):
    def test_translation_lock_commit_rollback_and_tls(self):
        from unittest.mock import MagicMock, patch
        import types
        from web.postgres import Connection
        driver = types.ModuleType('psycopg')
        driver.connect = MagicMock()
        with patch.dict('sys.modules', {'psycopg':driver}):
            with Connection('test-url') as db:
                db.executescript('CREATE TABLE trades (id INTEGER PRIMARY KEY);')
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT OR IGNORE INTO accounts VALUES (?,?)',('demo:TRY',100))
            driver.connect.assert_called_once_with('test-url',connect_timeout=10,sslmode='verify-full')
            calls = driver.connect.return_value.execute.call_args_list
            self.assertIn('GENERATED ALWAYS AS IDENTITY',calls[0].args[0])
            self.assertIn('pg_advisory_xact_lock',calls[1].args[0])
            self.assertEqual(calls[2].args,('INSERT INTO accounts VALUES (%s,%s) ON CONFLICT DO NOTHING',('demo:TRY',100)))
            driver.connect.return_value.commit.assert_called_once()
            with self.assertRaises(RuntimeError):
                with Connection('test-url'):
                    raise RuntimeError('rollback')
            driver.connect.return_value.rollback.assert_called_once()

if __name__ == '__main__':
    unittest.main()
