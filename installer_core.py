"""Fresh-machine installer. No installation is performed on import."""
from dataclasses import dataclass, field
import ctypes
import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import time
import urllib.request

VERSION = '0.6.1-preview'
SCRIPTS = ('Install-SystemTask.ps1', 'Run-SystemTask.ps1', 'Collect-EndpointSessions.ps1',
           'Export-DirectoryInventory.ps1', 'Send-DirectoryInventory.ps1', 'Send-Report.ps1', 'Setup-Network.ps1', 'Detect-Networks.ps1')


@dataclass
class Options:
    target: str
    username: str
    password: str = field(repr=False)
    port: int = 8765
    mode: str = 'local'
    address: str = '127.0.0.1'
    hostname: str = 'localhost'
    language: str = 'tr'
    endpoint: bool = True
    directory: bool = False
    trust_ca: bool = True
    firewall: bool = False
    auto_discover: bool = True


def validate(options):
    target = Path(options.target)
    if not target.is_absolute() or target == Path(target.anchor) or '"' in str(target):
        raise ValueError('Choose an absolute, dedicated application folder.')
    for parent in (target, *target.parents):
        if parent.exists() and (parent.is_symlink() or getattr(parent.stat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Symbolic links and junctions are not supported.')
    blocked = [Path(p).resolve() for p in (os.environ.get('WINDIR'), os.environ.get('ProgramFiles'), os.environ.get('USERPROFILE')) if p]
    if target.resolve() in blocked:
        raise ValueError('Choose an application subfolder, not a system/user root.')
    if target.exists() and any(target.iterdir()):
        raise ValueError('Folder is not empty. This preview supports fresh installation only.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', options.username) or not 12 <= len(options.password) <= 256:
        raise ValueError('Username: 3–64 letters/digits/._-; password: 12–256 characters.')
    if type(options.port) is not int or not 1024 <= options.port <= 65535:
        raise ValueError('Choose a port between 1024 and 65535.')
    if options.language not in ('tr', 'en', 'fr', 'de') or options.mode not in ('local', 'lan'):
        raise ValueError('Invalid language or access mode.')
    address = ipaddress.ip_address(options.address)
    if address.version != 4 or (options.mode == 'local' and str(address) != '127.0.0.1'):
        raise ValueError('Local mode must use 127.0.0.1. This installer requires IPv4.')
    if options.mode == 'lan' and (not address.is_private or address.is_loopback or address.is_unspecified):
        raise ValueError('LAN mode requires a private local interface address, not 0.0.0.0.')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', options.hostname):
        raise ValueError('Enter a valid panel hostname.')
    if not options.trust_ca:
        raise ValueError('Automatic setup requires trusting the generated, scoped local CA.')
    return target.resolve()


def powershell(script, *arguments, cwd=None):
    command = [str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
               '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'RemoteSigned', '-WindowStyle', 'Hidden', '-File', str(script), *map(str, arguments)]
    result = subprocess.run(command, cwd=cwd, capture_output=True, timeout=180,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        # Do not put potentially sensitive subprocess output into exception/UI text.
        raise RuntimeError('Windows configuration step failed. Check installation logs and task permissions.')


def install(options, executable, assets, progress=lambda message: None):
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError('Run the installer as administrator.')
    target = validate(options)
    executable, assets = Path(executable).resolve(), Path(assets).resolve()
    if not executable.is_file() or not (assets / 'web/index.html').is_file() or any(not (assets / s).is_file() for s in SCRIPTS):
        raise ValueError('Installation payload is incomplete.')
    if not (executable.parent / '_internal').is_dir():
        raise ValueError('Extract the complete package, including the _internal folder.')
    powershell(assets / 'Setup-Network.ps1', '-CheckTasks')
    if options.directory:
        powershell(assets / 'Setup-Network.ps1', '-CheckDirectory')
    # Refuse port conflicts before touching the destination.
    with socket.socket() as check:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        check.bind((options.address, options.port))
    parent = target.parent
    while not parent.exists():
        parent = parent.parent
    if shutil.disk_usage(parent).free < max(600 * 1024**2, executable.stat().st_size * 4):
        raise ValueError('At least 600 MB free disk space is required.')
    target.mkdir(parents=True, exist_ok=True)
    log_folder = target / 'data/logs'
    log_folder.mkdir(parents=True)
    manifest = {'product': 'CenterEK', 'version': VERSION, 'status': 'installing',
                'installed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'completed': []}
    manifest_path = target / 'installation.local.json'
    def step(message):
        progress(message)
        manifest['completed'].append(message)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        with (log_folder / 'install.log').open('a', encoding='utf-8') as stream:
            stream.write(datetime.datetime.now(datetime.timezone.utc).isoformat() + ' ' + message + '\n')
    try:
        step('Copying application and web assets')
        installed_exe = target / 'CenterEK.exe'
        shutil.copy2(executable, installed_exe)
        runtime = executable.parent / '_internal'
        if not runtime.is_dir():
            raise ValueError('Bundled runtime folder is missing. Extract the complete ZIP first.')
        shutil.copytree(runtime, target / '_internal')
        shutil.copytree(assets / 'web', target / 'web')
        for page in ('index.html','login.html'):
            html=target/'web'/page
            html.write_text(html.read_text(encoding='utf-8').replace('lang="tr"','lang="'+options.language+'"'),encoding='utf-8')
        for name in SCRIPTS:
            shutil.copy2(assets / name, target / name)
        for name in ('INSTALLATION.md', 'THIRD-PARTY.txt'):
            if (assets / name).is_file():
                shutil.copy2(assets / name, target / name)
        from file_security import restrict
        restrict(target, directory=True)
        step('Creating local administrator and database')
        import auth
        import agents
        import monitor
        import service_secrets
        store = monitor.Store(target / 'data/monitor.sqlite3')
        try:
            auth.Auth(store).add_user(options.username, options.password, 'admin')
            computer = socket.gethostname().upper()
            config = {'interval': 30, 'threshold': 3, 'timeout': 2, 'devices': [{
                'id': 'local-host', 'name': computer, 'host': options.address, 'kind': 'Sunucu',
                'method': 'tcp', 'port': options.port, 'agent_computer': computer}]}
            config['discovery'] = {'enabled': options.auto_discover, 'auto_add': options.auto_discover}
            monitor.validate(config)
            (target / 'config.local.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
            step('Generating scoped HTTPS certificates')
            import tls_setup
            certificate_folder = target / 'certs/panel'
            tls_setup.create(certificate_folder, options.hostname, list(dict.fromkeys(['127.0.0.1', options.address])))
            network = {'bind': options.address, 'port': options.port,
                       'tls_cert': 'certs/panel/panel-cert.pem', 'tls_key': 'certs/panel/panel-key.pem'}
            (target / 'server.local.json').write_text(json.dumps(network, indent=2), encoding='utf-8')
            url = 'https://' + options.address + ':' + str(options.port)
            registry = agents.Registry(store, target)
            configs = {}
            for kind, enabled in [('endpoint', options.endpoint), ('directory', options.directory)]:
                if not enabled:
                    continue
                entry = registry.register(computer, kind)
                token = entry.pop('token')
                entry.update(url=url, token_machine=service_secrets.protect(token))
                secure = target / 'data/secure'
                secure.mkdir(exist_ok=True)
                restrict(secure, directory=True)
                path = secure / (kind + '.bootstrap.local.json')
                path.write_text(json.dumps(entry), encoding='utf-8')
                restrict(path)
                configs[kind] = path
                token = None
        finally:
            store.db.close()
        step('Installing Windows startup tasks and certificate trust')
        helper = target / 'Install-SystemTask.ps1'
        # Import before starting the endpoint tasks; the installer selection is explicit.
        result = subprocess.run(['certutil.exe', '-addstore', 'Root', str(certificate_folder / 'panel-ca.pem')],
                                capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError('Windows could not trust the generated panel CA.')
        powershell(helper, '-Mode', 'Server', '-ServerExecutable', installed_exe, cwd=target)
        for kind, path in configs.items():
            powershell(helper, '-Mode', kind.capitalize(), '-AgentConfig', path,
                       '-CACertificate', certificate_folder / 'panel-ca.pem', '-ServerExecutable', installed_exe, cwd=target)
            path.unlink(missing_ok=True)
        if options.firewall and options.mode == 'lan':
            step('Allowing selected LAN port on private/domain profiles')
            powershell(assets / 'Setup-Network.ps1', '-Address', options.address, '-Port', options.port, cwd=target)
        step('Checking HTTPS readiness')
        context = ssl.create_default_context(cafile=str(certificate_folder / 'panel-ca.pem'))
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
        ready = False
        for _ in range(45):
            try:
                with client.open(url + '/login', timeout=2) as response:
                    ready = response.status == 200
                if ready:
                    break
            except (OSError, ValueError):
                time.sleep(2)
        if not ready:
            raise RuntimeError('Application did not become ready. Inspect data/logs/server.log and application.log.')
        shortcut = Path(os.environ.get('ProgramData', r'C:\ProgramData')) / 'Microsoft/Windows/Start Menu/Programs/CenterEK'
        shortcut.mkdir(exist_ok=True)
        (shortcut / 'CenterEK.url').write_text('[InternetShortcut]\nURL=' + url + '\n', encoding='utf-8')
        manifest.update(status='ready', url=url, access_mode=options.mode, language=options.language)
        step('Installation completed')
        return url
    except Exception as error:
        manifest.update(status='failed', error_type=type(error).__name__)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        # Keep the data and precise completed-step record for recovery; do not delete it.
        raise
