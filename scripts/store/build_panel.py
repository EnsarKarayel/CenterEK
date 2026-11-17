"""Export fixed public PWA assets; this does not create an MSIX or publish an app."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
from urllib.parse import urlsplit
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import panel_app


def icon(size):
    """Render our three-bar vector mark deterministically, without third-party artwork."""
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            px, py = x * 512 // size, y * 512 // size
            color = (42, 73, 84)
            for left, top, rgb in ((128, 320, (115, 182, 130)), (224, 224, (98, 168, 203)), (320, 128, (255, 153, 51))):
                if left <= px < left + 64 and top <= py < 384:
                    color = rgb
            raw.extend(color)
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))


def export(output, origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('An HTTPS origin without path, credentials, query or fragment is required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    public = output / 'public'
    hashes = {}
    for route, (name, _) in panel_app.FILES.items():
        relative = 'panel/index.html' if route == '/panel/' else route.lstrip('/')
        target = public / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / 'web/panel' / name).read_bytes())
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    report = {'kind': 'store-panel-web-assets', 'store_ready': False, 'msix_created': False,
              'origin': origin.rstrip('/'), 'start_url': origin.rstrip('/') + '/panel/',
              'files': hashes, 'pending': ['Partner Center product identity', 'Public HTTPS asset hosting',
                  'Production privacy policy', 'Dedicated review account/environment',
                  'PWABuilder Windows package', 'Entra and panel login acceptance', 'Store certification']}
    (output / 'preparation-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    shutil.make_archive(str(output / 'CenterEK-Panel-Web'), 'zip', public)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--generate-icons', action='store_true')
    args = parser.parse_args()
    if args.generate_icons:
        for size in (192, 512):
            (ROOT / f'web/panel/icon-{size}.png').write_bytes(icon(size))
    print(json.dumps(export(args.output, args.origin), indent=2))
