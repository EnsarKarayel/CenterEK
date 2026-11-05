"""Manage accounts locally; no account creation over the network."""
import argparse
import getpass
import auth
import monitor


def main():
    parser = argparse.ArgumentParser(description='CenterEK yerel kullanıcı oluşturma')
    parser.add_argument('action', choices=['add', 'list', 'reset-password', 'disable'])
    parser.add_argument('--role', choices=['admin', 'viewer'], default='viewer')
    args = parser.parse_args()
    (monitor.ROOT / 'data').mkdir(exist_ok=True)
    store = monitor.Store(monitor.ROOT / 'data' / 'monitor.sqlite3')
    accounts = auth.Auth(store)
    try:
        if args.action == 'list':
            for row in store.db.execute('SELECT username,role,enabled FROM users ORDER BY username'):
                print(row['username'], row['role'], 'aktif' if row['enabled'] else 'devre dışı')
            return
        username = input('Kullanıcı adı: ').strip()
        if args.action == 'disable':
            with store.lock, store.db:
                row = store.db.execute('SELECT role,enabled FROM users WHERE username=?', (username,)).fetchone()
                admins = store.db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND enabled=1").fetchone()[0]
                if row and row['role'] == 'admin' and row['enabled'] and admins <= 1:
                    raise ValueError('Son aktif yönetici devre dışı bırakılamaz')
                if not row:
                    raise ValueError('Kullanıcı bulunamadı')
                store.db.execute('UPDATE users SET enabled=0 WHERE username=?', (username,))
            print('Devre dışı bırakıldı. Eski oturumlar sonraki istekte reddedilir.')
            return
        password = getpass.getpass('Parola (en az 12 karakter): ')
        if password != getpass.getpass('Parola tekrar: '):
            raise ValueError('Parolalar eşleşmiyor')
        if args.action == 'add':
            accounts.add_user(username, password, args.role)
        else:
            if not 12 <= len(password) <= 256:
                raise ValueError('Parola 12-256 karakter olmalı')
            salt, digest, iterations = accounts.hash_password(password)
            with store.lock, store.db:
                cursor = store.db.execute('UPDATE users SET salt=?,digest=?,iterations=? WHERE username=?',
                                          (salt, digest, iterations, username))
                if not cursor.rowcount:
                    raise ValueError('Kullanıcı bulunamadı')
        print('Kaydedildi. Parolası değişen hesabın eski oturumları sonraki istekte reddedilir.')
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
