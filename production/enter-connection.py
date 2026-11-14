#!/usr/bin/env python3
"""Server-console input for a linked-account service: twitch, github or battlenet.

    sudo python3 enter-connection.py twitch|github|battlenet [--replace]

Asks for the client id and client secret from that service's developer
console, typed at the console and never echoed, logged or printed, and writes
/etc/zrzur/<service>.json (mode 600). prepare-config.py reads it into
[api.connections.<service>] of /etc/zrzur/Revolt.toml. For Twitch it also
makes the secret Twitch signs live/offline messages with (never typed, never
shown). An existing file is kept unless --replace is given. Without the file
the service stays off: Settings -> Connections says it can't be linked yet.

Where the values come from (redirect address to register there:
https://app.zrzur.com/connections/<service>/return, and the beta one):
  twitch     https://dev.twitch.tv/console  (Register Your Application)
  github     https://github.com/settings/developers  (OAuth Apps)
  battlenet  https://community.developer.battle.net/access/clients
"""
from getpass import getpass
import json
import os
import re
import secrets
import sys
from pathlib import Path

SERVICES = {
    'twitch': 'Twitch',
    'github': 'GitHub',
    'battlenet': 'Battle.net',
}
# Lenient shapes: the services do not promise exact lengths
CLIENT_ID = re.compile(r'^[A-Za-z0-9._-]{8,128}$')
CLIENT_SECRET = re.compile(r'^[A-Za-z0-9._~-]{16,128}$')


def main():
    args = sys.argv[1:]
    service = next((a for a in args if not a.startswith('--')), '')
    if service not in SERVICES:
        raise SystemExit('Usage: sudo python3 enter-connection.py twitch|github|battlenet [--replace]')
    name = SERVICES[service]

    directory = Path('/etc/zrzur')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = directory / f'{service}.json'
    if path.exists() and '--replace' not in args:
        raise SystemExit(f'{service}.json already exists; nothing changed. Use --replace to enter new {name} values.')

    client_id = getpass(f'{name} client id (hidden): ').strip()
    if not CLIENT_ID.match(client_id):
        raise SystemExit(f'That does not look like a {name} client id; nothing saved.')
    client_secret = getpass(f'{name} client secret (hidden): ').strip()
    if not CLIENT_SECRET.match(client_secret):
        raise SystemExit(f'That does not look like a {name} client secret; nothing saved.')
    if client_secret == client_id:
        raise SystemExit('The secret is the same as the client id; nothing saved.')

    values = {'client_id': client_id, 'client_secret': client_secret}
    if service == 'twitch':
        # Twitch signs live/offline messages with this; 10-100 characters
        values['eventsub_secret'] = secrets.token_urlsafe(48)[:64]

    tmp = directory / f'{service}.json.new'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(values, stream)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    print(f'{service.upper()}_READY: the {name} client id and secret are saved in {path} (mode 600).')


if __name__ == '__main__':
    main()
