"""Prompt credentials locally in memory, then start the monitor."""
import getpass
import json
import os
import sys
import monitor


def main():
    config = monitor.validate(json.loads((monitor.ROOT / 'config.local.json').read_text(encoding='utf-8-sig')))
    unattended = '--non-interactive' in sys.argv
    if unattended:
        sys.argv.remove('--non-interactive')
        from service_secrets import load
        path = monitor.ROOT / 'data' / 'secure' / 'service-secrets.local.json'
        if path.exists():
            os.environ.update(load(path))
    for device in config['devices']:
        for key, variable in device.get('collector', {}).items():
            if key.endswith('_env') and variable not in os.environ:
                if unattended:
                    raise SystemExit('Eksik arka plan kimlik bilgisi: ' + variable + '. service_secrets.py çalıştırın.')
                prompt = device['name'] + ' (' + key[:-4] + '): '
                os.environ[variable] = input(prompt) if key == 'username_env' else getpass.getpass(prompt)
    monitor.main()


if __name__ == '__main__':
    main()
