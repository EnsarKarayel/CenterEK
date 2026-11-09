"""Build a secret-free office relay bundle from an explicit file allowlist."""
import hashlib
import json
from pathlib import Path
import zipfile

FILES = ('site_push.py', 'site_relay.py', 'agents.py', 'service_secrets.py',
         'file_security.py', 'Install-SiteRelay.ps1', 'Run-SiteRelay.ps1')

def build(root, output):
    root, output = Path(root), Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'schema': 1, 'files': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in FILES}}
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(root/name, name)
        archive.writestr('relay-manifest.json', json.dumps(manifest, indent=2))
    return manifest

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1], args.output)
    print('Secret-free relay bundle created:', args.output)
