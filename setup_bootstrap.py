"""Single-file delivery wrapper for the bundled installer; no system Python needed."""
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def extract_payload(archive, target):
    target = Path(target).resolve()
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            path = (target / entry.filename).resolve()
            if not path.is_relative_to(target) or '\\' in entry.filename or ':' in entry.filename:
                raise ValueError('Invalid setup payload path')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Setup payload cannot contain symbolic links')
        package.extractall(target)
    executable = target / 'CenterEK-Setup' / 'CenterEK-Setup.exe'
    if not executable.is_file() or not (executable.parent / '_internal').is_dir():
        raise ValueError('Incomplete setup payload')
    return executable


def main():
    assets = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    with tempfile.TemporaryDirectory(prefix='CenterEK-Setup-') as folder:
        executable = extract_payload(assets / 'installer-payload.zip', folder)
        # Keep the runtime available until the customer closes the wizard.
        return subprocess.run([str(executable)], cwd=executable.parent, check=False).returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, 'CenterEK kurulumu başlatılamadı. Kurulum dosyasını yeniden indirin ve disk alanını kontrol edin.', 'CenterEK Setup', 16)
        raise SystemExit(1)
