#!/usr/bin/env python3
"""Interactive server-console input; credentials never enter shell history or output."""
from getpass import getpass
import json
import os
from pathlib import Path

directory = Path('/etc/zrzur')
directory.mkdir(parents=True, mode=0o700, exist_ok=True)
os.chmod(directory, 0o700)
path = directory / 'storage.json'
if path.exists():
    raise SystemExit('Storage configuration already exists; no changes made.')
values = {
    'access_key_id': getpass('S3 Access Key (hidden): ').strip(),
    'secret_access_key': getpass('S3 Secret Key (hidden): ').strip(),
    'endpoint': os.environ.get('ZRZUR_S3_ENDPOINT', '').strip(),
    'region': 'us-east-1',
    'default_bucket': 'zrzur',
    'path_style_buckets': False,
}
if not values['endpoint']:
    raise SystemExit('Set ZRZUR_S3_ENDPOINT to your S3 endpoint; nothing saved.')
if not values['access_key_id'] or not values['secret_access_key']:
    raise SystemExit('Empty input; nothing saved.')
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump(values, stream)
print('S3_READY: protected credentials saved; connection verification follows separately.')
