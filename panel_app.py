"""Public, fixed PWA assets only. Panel APIs retain their existing authentication."""
from pathlib import Path

FILES = {
    '/panel/': ('index.html', 'text/html; charset=utf-8'),
    '/panel/manifest.webmanifest': ('manifest.webmanifest', 'application/manifest+json; charset=utf-8'),
    '/panel/panel.js': ('panel.js', 'text/javascript; charset=utf-8'),
    '/panel/panel.css': ('panel.css', 'text/css; charset=utf-8'),
    '/panel/offline.html': ('offline.html', 'text/html; charset=utf-8'),
    '/panel/privacy.html': ('privacy.html', 'text/html; charset=utf-8'),
    '/panel/support.html': ('support.html', 'text/html; charset=utf-8'),
    '/panel/icon.svg': ('icon.svg', 'image/svg+xml'),
    '/panel/icon-192.png': ('icon-192.png', 'image/png'),
    '/panel/icon-512.png': ('icon-512.png', 'image/png'),
    '/panel-worker.js': ('worker.js', 'text/javascript; charset=utf-8'),
}


def respond(handler, web_root):
    if handler.path == '/panel':
        handler.respond(308, b'', headers={'Location': '/panel/'})
        return True
    asset = FILES.get(handler.path)
    if asset is None:
        return False
    name, mime = asset
    path = Path(web_root) / 'panel' / name
    if not path.is_file():
        handler.respond(404, b'{}')
        return True
    headers = {'Service-Worker-Allowed': '/'} if name == 'worker.js' else {}
    handler.respond(200, path.read_bytes(), mime, headers=headers)
    return True
