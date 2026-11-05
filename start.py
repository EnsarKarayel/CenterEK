"""Prompt credentials locally in memory, then start the monitor."""
import getpass
import json
import os
import monitor


def main():
    config = monitor.validate(json.loads((monitor.ROOT / 'config.local.json').read_text(encoding='utf-8-sig')))
    for device in config['devices']:
        for key, variable in device.get('collector', {}).items():
            if key.endswith('_env') and variable not in os.environ:
                prompt = device['name'] + ' (' + key[:-4] + '): '
                os.environ[variable] = input(prompt) if key == 'username_env' else getpass.getpass(prompt)
    monitor.main()


if __name__ == '__main__':
    main()
