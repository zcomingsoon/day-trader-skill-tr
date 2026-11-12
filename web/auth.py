"""Single-owner authentication. Only a salted password hash belongs in configuration."""
import getpass
import hashlib
import hmac
import os
import secrets
import threading
import time
from http.cookies import SimpleCookie


def password_hash(password, salt=None):
    if len(password) < 14:
        raise ValueError('En az 14 karakterli bir parola gerekli.')
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return 'pbkdf2-sha256$' + salt + '$' + digest


class Auth:
    def __init__(self, encoded, secure=True):
        try:
            algorithm, salt, digest = encoded.split('$')
            if algorithm != 'pbkdf2-sha256' or len(bytes.fromhex(salt)) != 16 or len(bytes.fromhex(digest)) != 32:
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValueError('PAPER_PASSWORD_HASH geçerli bir pbkdf2-sha256 özeti olmalı.') from None
        self.encoded = encoded
        self.secure = secure
        self.sessions = {}
        self.failures = []
        self.lock = threading.Lock()

    def login(self, password):
        with self.lock:
            now = time.monotonic()
            self.failures = [t for t in self.failures if now-t < 300]
            if len(self.failures) >= 5:
                return 429, None
            if not isinstance(password, str) or len(password) > 1024:
                self.failures.append(now)
                return 401, None
            valid = hmac.compare_digest(password_hash(password, self.encoded.split('$')[1]) if len(password) >= 14 else '', self.encoded)
            if not valid:
                self.failures.append(now)
                return 401, None
            self.sessions = {k:v for k,v in self.sessions.items() if v[0] > now}
            if len(self.sessions) >= 20:
                self.sessions.pop(next(iter(self.sessions)))
            sid = secrets.token_urlsafe(32)
            self.sessions[sid] = (now+43200, secrets.token_urlsafe(32))
            return 200, sid

    def sid(self, headers):
        try:
            cookie = SimpleCookie(headers.get('Cookie', ''))
            return cookie['paper_session'].value if 'paper_session' in cookie else ''
        except Exception:
            return ''

    def session(self, headers):
        with self.lock:
            sid = self.sid(headers)
            session = self.sessions.get(sid)
            if session and session[0] > time.monotonic():
                return session[1]
            self.sessions.pop(sid, None)
            return None

    def logout(self, headers):
        with self.lock:
            self.sessions.pop(self.sid(headers), None)

    def cookie(self, sid='', expired=False):
        return 'paper_session=' + sid + '; Path=/; HttpOnly; SameSite=Strict; Max-Age=' + ('0' if expired else '43200') + ('; Secure' if self.secure else '')


if __name__ == '__main__':
    first = getpass.getpass('Yeni parola (en az 14 karakter): ')
    if first != getpass.getpass('Parolayı tekrar girin: '):
        raise SystemExit('Parolalar eşleşmiyor.')
    print(password_hash(first))
