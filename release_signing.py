"""Authenticode integration; private keys remain in the operator's certificate provider."""
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
from installer_core import powershell_env


def sign(path, thumbprint, timestamp_url, signtool):
    if not re.fullmatch('[A-Fa-f0-9]{40}', thumbprint):
        raise ValueError('A certificate SHA1 thumbprint is required (file signing still uses SHA256)')
    uri = urlsplit(timestamp_url)
    if uri.scheme != 'https' or not uri.hostname or uri.username or uri.password:
        raise ValueError('An HTTPS timestamp endpoint is required')
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Signing target is missing')
    if path.suffix.lower() == '.ps1':
        # Paths are passed through the child environment, never interpolated as code.
        script = "$ErrorActionPreference='Stop'; $c=Get-Item -LiteralPath ('Cert:\\CurrentUser\\My\\'+$env:CENTEREK_SIGN_THUMBPRINT); $s=Set-AuthenticodeSignature -LiteralPath $env:CENTEREK_SIGN_PATH -Certificate $c -HashAlgorithm SHA256 -TimestampServer $env:CENTEREK_TIMESTAMP; if($s.Status -ne 'Valid' -or -not $s.TimeStamperCertificate){throw 'Script signing or timestamp failed'}"
        command = [str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'), '-NoProfile', '-NonInteractive', '-Command', script]
        env = powershell_env(CENTEREK_SIGN_PATH=str(path), CENTEREK_SIGN_THUMBPRINT=thumbprint, CENTEREK_TIMESTAMP=timestamp_url)
        result = subprocess.run(command, env=env, capture_output=True, timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        result = subprocess.run([str(signtool), 'sign', '/s', 'My', '/sha1', thumbprint, '/fd', 'SHA256', '/tr', timestamp_url, '/td', 'SHA256', str(path)], capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError('Authenticode signing failed; no commercial release may be published')
    return verify(path, thumbprint)


def verify(path, thumbprint):
    script = "$ErrorActionPreference='Stop'; $s=Get-AuthenticodeSignature -LiteralPath $env:CENTEREK_SIGN_PATH; if($s.Status -ne 'Valid' -or $s.SignerCertificate.Thumbprint -ine $env:CENTEREK_SIGN_THUMBPRINT -or -not $s.TimeStamperCertificate){throw 'Untrusted, wrong-publisher, or untimestamped signature'}; @{status='Valid';thumbprint=$s.SignerCertificate.Thumbprint;timestamped=$true}|ConvertTo-Json -Compress"
    command = [str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'), '-NoProfile', '-NonInteractive', '-Command', script]
    result = subprocess.run(command, env=powershell_env(CENTEREK_SIGN_PATH=str(Path(path).resolve()), CENTEREK_SIGN_THUMBPRINT=thumbprint), capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Trusted publisher signature verification failed')
    return json.loads(result.stdout.decode('utf-8-sig'))
