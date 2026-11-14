#!/usr/bin/env python3
"""Server-console input for the KLIPY GIF key.

Writes /etc/zrzur/gifbox.env (mode 600) with GIFBOX_KLIPY_KEY, typed at the
console and never echoed, logged or printed, and GIFBOX_MEDIA_SECRET, made
here at random (the GIF service signs its media links with it). Run with sudo.
An existing file is kept unless --replace-key is given; the media secret is
kept across a key change so links already sent keep working.
"""
from getpass import getpass
import os
import secrets
import sys
from pathlib import Path

directory = Path('/etc/zrzur')
directory.mkdir(parents=True, mode=0o700, exist_ok=True)
path = directory / 'gifbox.env'
replace = '--replace-key' in sys.argv[1:]

media_secret = None
if path.exists():
    if not replace:
        raise SystemExit('gifbox.env already exists; nothing changed. Use --replace-key to enter a new KLIPY key.')
    for line in path.read_text().splitlines():
        if line.startswith('GIFBOX_MEDIA_SECRET='):
            media_secret = line.split('=', 1)[1].strip() or None

key = getpass('KLIPY API key (hidden): ').strip()
if not key:
    raise SystemExit('No key entered; nothing saved.')
if any(c.isspace() or c in '"\'\\$`' for c in key):
    raise SystemExit('The key has characters a key never has (spaces, quotes, $); nothing saved.')
if not media_secret or len(media_secret) < 16:
    media_secret = secrets.token_urlsafe(48)

tmp = directory / 'gifbox.env.new'
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as stream:
    stream.write(f'GIFBOX_KLIPY_KEY={key}\nGIFBOX_MEDIA_SECRET={media_secret}\n')
os.replace(tmp, path)
os.chmod(path, 0o600)
print('GIFBOX_READY: the KLIPY key and the media secret are saved in /etc/zrzur/gifbox.env (mode 600).')
