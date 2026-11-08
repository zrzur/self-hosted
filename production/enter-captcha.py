#!/usr/bin/env python3
"""Interactive server-console input for the hCaptcha keys; the secret is never echoed, logged or printed."""
from getpass import getpass
import json
import os
from pathlib import Path

directory = Path('/etc/zrzur')
directory.mkdir(parents=True, mode=0o700, exist_ok=True)
path = directory / 'captcha.json'
if path.exists():
    raise SystemExit('Captcha configuration already exists; no changes made.')
sitekey = input('hCaptcha site key (public): ').strip()
secret = getpass('hCaptcha secret key (hidden): ').strip()
if not sitekey or not secret:
    raise SystemExit('Both keys are needed; nothing saved.')
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump({'sitekey': sitekey, 'secret': secret}, stream)
print('CAPTCHA_READY: protected hCaptcha keys saved; regenerate the configuration to enable the captcha.')
