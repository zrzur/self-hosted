#!/usr/bin/env python3
"""Server-console input for the Steam Web API key (linked Steam accounts).

Writes /etc/zrzur/steam.json (mode 600) with the key, typed at the console
and never echoed, logged or printed. prepare-config.py reads it into
[api.connections.steam] of /etc/zrzur/Revolt.toml. Run with sudo. An existing
file is kept unless --replace-key is given. The key comes from
https://steamcommunity.com/dev/apikey and belongs only in this file.
"""
from getpass import getpass
import json
import os
import string
import sys
from pathlib import Path

directory = Path('/etc/zrzur')
directory.mkdir(parents=True, mode=0o700, exist_ok=True)
path = directory / 'steam.json'

if path.exists() and '--replace-key' not in sys.argv[1:]:
    raise SystemExit('steam.json already exists; nothing changed. Use --replace-key to enter a new Steam key.')

key = getpass('Steam Web API key (hidden): ').strip()
if not key:
    raise SystemExit('No key entered; nothing saved.')
# Steam keys are 32 hexadecimal characters
if len(key) != 32 or any(c not in string.hexdigits for c in key):
    raise SystemExit('That does not look like a Steam Web API key (32 letters 0-9 and A-F); nothing saved.')

tmp = directory / 'steam.json.new'
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump({'web_api_key': key.upper()}, stream)
os.replace(tmp, path)
os.chmod(path, 0o600)
print('STEAM_READY: the Steam Web API key is saved in /etc/zrzur/steam.json (mode 600).')
