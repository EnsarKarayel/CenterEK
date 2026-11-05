"""Local accounts and revocable, fixed-lifetime sessions."""
import hashlib
import hmac
import secrets
import threading
import time

ITERATIONS = 600000


class Auth:
    def __init__(self, store, secure=False, public_origin=None):
        self.store = store
        self.secure = secure
        self.public_origin = public_origin
        self.sessions = {}
        self.attempts = {}
        self.lock = threading.RLock()
        self.dummy = self.hash_password('dummy-password-for-timing')
        with store.lock, store.db:
            store.db.execute('''CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, salt TEXT, digest TEXT, iterations INTEGER,
                role TEXT, enabled INTEGER DEFAULT 1)''')

    @staticmethod
    def hash_password(password, salt=None, iterations=ITERATIONS):
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), iterations).hex()
        return salt, digest, iterations

    def add_user(self, username, password, role='viewer'):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', username) or not 12 <= len(password) <= 256:
            raise ValueError('Kullanıcı adı 3-64 uygun karakter, parola 12-256 karakter olmalı')
        if role not in ('admin', 'viewer'):
            raise ValueError('Geçersiz rol')
        salt, digest, iterations = self.hash_password(password)
        with self.store.lock, self.store.db:
            self.store.db.execute('INSERT INTO users VALUES (?,?,?,?,?,1)', (username, salt, digest, iterations, role))

    def count(self):
        with self.store.lock:
            return self.store.db.execute('SELECT COUNT(*) FROM users WHERE enabled=1').fetchone()[0]

    def login(self, username, password, address):
        now = time.time()
        # Hold this lock through verification so concurrent requests cannot race
        # past the attempt threshold. Accounts are changed only through local CLI.
        with self.lock:
            self.attempts = {k: v for k, v in self.attempts.items() if v[1] > now}
            count, until = self.attempts.get(address, (0, now + 300))
            if count >= 5:
                return None, 'limited'
            with self.store.lock:
                row = self.store.db.execute('SELECT * FROM users WHERE username=? AND enabled=1', (username,)).fetchone()
            salt, digest, iterations = (row['salt'], row['digest'], row['iterations']) if row else self.dummy
            check = self.hash_password(password, salt, iterations)[1]
            if not hmac.compare_digest(check, digest) or not row:
                self.attempts[address] = (count + 1, until)
                return None, 'invalid'
            self.attempts.pop(address, None)
            token = secrets.token_urlsafe(32)
            self.sessions = {k: v for k, v in self.sessions.items() if v['expires'] > now}
            # Bound memory without evicting every existing session on each login.
            if len(self.sessions) >= 1000:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = {
                'username': username, 'role': row['role'], 'expires': now + 8 * 3600, 'credential': digest}
            return token, None

    def user(self, token):
        if not token or len(token) > 128:
            return None
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            user = self.sessions.get(key)
            if not user or user['expires'] <= time.time():
                self.sessions.pop(key, None)
                return None
            with self.store.lock:
                row = self.store.db.execute('SELECT enabled,digest FROM users WHERE username=?', (user['username'],)).fetchone()
            if not row or not row['enabled'] or not hmac.compare_digest(row['digest'], user['credential']):
                self.sessions.pop(key, None)
                return None
            return {k: user[k] for k in ('username', 'role', 'expires')}

    def logout(self, token):
        with self.lock:
            self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)

    def cookie(self, token='', clear=False):
        return ('centerek_session=' + token + '; Path=/; HttpOnly; SameSite=Strict; Max-Age=' +
                ('0' if clear else '28800') + ('; Secure' if self.secure else ''))
