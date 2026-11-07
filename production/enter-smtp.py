#!/usr/bin/env python3
"""Interactive server-console input for the Resend SMTP key; never echoed, logged or printed."""
from getpass import getpass
import json
import os
from pathlib import Path

directory = Path('/etc/zrzur')
directory.mkdir(parents=True, mode=0o700, exist_ok=True)
path = directory / 'smtp.json'
if path.exists():
    raise SystemExit('SMTP configuration already exists; no changes made.')
key = getpass('Resend API key (hidden): ').strip()
if not key.startswith('re_'):
    raise SystemExit('That does not look like a Resend API key (re_...); nothing saved.')
values = {
    'host': 'smtp.resend.com',
    'port': 465,
    'username': 'resend',
    'password': key,
    'from_address': 'Zrzur <no-reply@zrzur.com>',
}
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump(values, stream)
print('SMTP_READY: protected Resend key saved; regenerate the configuration to enable email.')
