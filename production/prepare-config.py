#!/usr/bin/env python3
"""Generate protected Zrzur main-server configuration in /etc/zrzur.

Inputs (root-only, written beforehand without echoing values):
  /etc/zrzur/storage.json  from enter-storage.py
  /etc/zrzur/voice.json    LiveKit key/secret of the voice server

Never prints secrets and never starts services. Existing secret files are kept; a differing
generated file stops the script for review instead of being replaced.
"""
import base64
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.request

DIRECTORY = Path('/etc/zrzur')
CADDY = DIRECTORY / 'caddy'
NONROOT_GID = 65532  # distroless nonroot group used by the backend images


def caddy_files(networks):
    """The generated Caddy rules, by file name in /etc/zrzur/caddy."""
    return {
        'trusted-proxies.caddy': f'trusted_proxies static {networks}\n',
        # a handle block: Caddy runs handle before a bare respond, so a bare
        # respond would let everything through on sites that use handle
        'cloudflare-only.caddy': f'@untrusted_origin not remote_ip {networks}\nhandle @untrusted_origin {{\n\trespond 403\n}}\n',
    }


def write_protected(path, content, group=None):
    if path.exists() and path.read_text() != content:
        raise SystemExit(f'Existing {path} differs; review before replacement.')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)
    if group is not None:
        os.chown(path, 0, group)
        os.chmod(path, 0o640)


def application_secrets():
    path = DIRECTORY / 'application-secrets.json'
    if not path.exists():
        pem = subprocess.check_output(['openssl', 'ecparam', '-name', 'prime256v1', '-genkey', '-noout'], stderr=subprocess.DEVNULL)
        public = subprocess.check_output(['openssl', 'ec', '-pubout', '-outform', 'DER'], input=pem, stderr=subprocess.DEVNULL)[-65:]
        values = {name: secrets.token_hex(32) for name in ['mongo', 'redis', 'rabbit']}
        values.update(
            encryption=base64.b64encode(secrets.token_bytes(32)).decode(),
            vapid_private=base64.urlsafe_b64encode(pem).decode().rstrip('='),
            vapid_public=base64.urlsafe_b64encode(public).decode().rstrip('='),
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(values, stream)
    values = json.loads(path.read_text())
    added = False
    if 'internal' not in values:
        # added later: the secret the public sites send the API (rate-limit bucket)
        values['internal'] = secrets.token_hex(32)
        added = True
    if 'proxy' not in values:
        # added later: signs media proxy tickets; without it the API refuses
        # POST /auth/session/proxy_ticket (FeatureDisabled) and proxied media fails
        values['proxy'] = secrets.token_hex(32)
        added = True
    if added:
        path.write_text(json.dumps(values))
    return values


def cloudflare_networks():
    networks = []
    for version in ['v4', 'v6']:
        # Cloudflare answers 403 to the default Python-urllib user agent.
        request = urllib.request.Request(f'https://www.cloudflare.com/ips-{version}', headers={'User-Agent': 'zrzur-prepare-config/1'})
        response = urllib.request.urlopen(request, timeout=20)
        found = [str(ipaddress.ip_network(line.strip())) for line in response.read().decode().splitlines() if line.strip()]
        if not found:
            raise SystemExit('Cloudflare IP list empty; refusing unprotected proxy configuration.')
        networks.extend(found)
    return ' '.join(networks)


def main():
    DIRECTORY.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(DIRECTORY, 0o700)
    storage = json.loads((DIRECTORY / 'storage.json').read_text())
    voice = json.loads((DIRECTORY / 'voice.json').read_text())
    values = application_secrets()
    q = json.dumps
    # Email stays off (no verification mail) until enter-smtp.py has stored a sending key.
    smtp_path = DIRECTORY / 'smtp.json'
    smtp = json.loads(smtp_path.read_text()) if smtp_path.exists() else None
    if smtp:
        smtp_block = (f'host = {q(smtp["host"])}\nport = {int(smtp["port"])}\nusername = {q(smtp["username"])}\n'
                      f'password = {q(smtp["password"])}\nfrom_address = {q(smtp["from_address"])}')
    else:
        smtp_block = 'host = ""\nfrom_address = "no-reply@zrzur.com"'
    configuration = f'''production = true
environment = "staging"
[database]
mongodb = "mongodb://zrzur:{values['mongo']}@database:27017/?authSource=admin"
redis = "redis://:{values['redis']}@redis:6379/"
[hosts]
app = "https://app.zrzur.com"
api = "https://api.zrzur.com"
events = "wss://events.zrzur.com"
autumn = "https://cdn.zrzur.com"
january = "http://january:14705"
january_public = "https://api.zrzur.com/january"
assets = "https://app.zrzur.com/assets"
[hosts.livekit]
fra = "wss://voice.zrzur.com"
[rabbit]
host = "rabbit"
port = 5672
username = "zrzur"
password = "{values['rabbit']}"
[api.registration]
invite_only = true
[api.smtp]
{smtp_block}
[api.security]
trust_cloudflare = true
easypwned = ""
staff_origins = ["http://localhost:8090"]
[api.livekit.nodes.fra]
url = "https://voice.zrzur.com"
lat = 50.11
lon = 8.68
key = {q(voice['key'])}
secret = {q(voice['secret'])}
[january]
proxy_key = {q(values['proxy'])}
[files]
encryption_key = {q(values['encryption'])}
[files.preview]
banners = [960, 540]
[files.s3]
endpoint = {q(storage['endpoint'])}
region = {q(storage['region'])}
path_style_buckets = {str(bool(storage.get('path_style_buckets', False))).lower()}
default_bucket = {q(storage.get('default_bucket', 'zrzur'))}
access_key_id = {q(storage['access_key_id'])}
secret_access_key = {q(storage['secret_access_key'])}
[pushd]
production = true
[pushd.vapid]
private_key = {q(values['vapid_private'])}
public_key = {q(values['vapid_public'])}
'''
    write_protected(DIRECTORY / 'Revolt.toml', configuration, group=NONROOT_GID)
    for name, content in {
        'mongo.env': f"MONGO_INITDB_ROOT_USERNAME=zrzur\nMONGO_INITDB_ROOT_PASSWORD={values['mongo']}\n",
        'redis.env': f"VALKEY_PASSWORD={values['redis']}\n",
        'rabbit.env': f"RABBITMQ_DEFAULT_USER=zrzur\nRABBITMQ_DEFAULT_PASS={values['rabbit']}\n",
        'internal.env': f"ZRZUR_INTERNAL_TOKEN={values['internal']}\n",
    }.items():
        write_protected(DIRECTORY / name, content)

    # Cloudflare ranges are public; refresh them on every run.
    CADDY.mkdir(mode=0o755, exist_ok=True)
    networks = cloudflare_networks()
    for name, content in caddy_files(networks).items():
        (CADDY / name).write_text(content)
    print('Protected configuration prepared; signup is invite-only and no services were started.')


if __name__ == '__main__':
    main()
