#!/usr/bin/env python3
"""Prepare LiveKit + Caddy for voice.zrzur.com in /opt/zrzur/voice. Secrets are generated
on the voice server and never printed. Starts nothing; run `docker compose up -d` there after review.

Copy credentials.json to /etc/zrzur/voice.json on the main server over SSH (never through chat)."""
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path('/opt/zrzur/voice')
# Public IPv4 of the voice server; pass it explicitly, e.g. ZRZUR_VOICE_IP=203.0.113.10
NODE_IP = os.environ.get('ZRZUR_VOICE_IP', '').strip()
if not NODE_IP:
    raise SystemExit('Set ZRZUR_VOICE_IP to the public IPv4 address of this voice server.')
# Signed LiveKit webhooks go to voice-ingress through the main server's API host (node name "fra").
WEBHOOK_URL = 'https://api.zrzur.com/ingress/fra'

ROOT.mkdir(parents=True, exist_ok=True)
os.chmod(ROOT, 0o700)
credentials = ROOT / 'credentials.json'
if not credentials.exists():
    fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'key': 'ZV' + secrets.token_hex(12), 'secret': secrets.token_urlsafe(48)}, stream)
values = json.loads(credentials.read_text())

livekit = f'''port: 7880
rtc:
  tcp_port: 7881
  udp_port: 7882
  use_external_ip: false
  node_ip: {NODE_IP}
keys:
  {values['key']}: {values['secret']}
webhook:
  api_key: {values['key']}
  urls:
    - {WEBHOOK_URL}
turn:
  enabled: true
  domain: voice.zrzur.com
  udp_port: 3478
logging:
  level: info
  json: true
'''
compose = '''name: zrzur-voice
services:
  livekit:
    image: livekit/livekit-server:v1.13.10
    command: ["--config", "/etc/livekit.yaml"]
    restart: unless-stopped
    ports:
      - "127.0.0.1:7880:7880"
      - "7881:7881/tcp"
      - "7882:7882/udp"
      - "3478:3478/udp"
    volumes:
      - ./livekit.yaml:/etc/livekit.yaml:ro
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    stop_grace_period: 60s
  proxy:
    image: caddy:2.11.7-alpine
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
volumes:
  caddy_data:
  caddy_config:
'''
proxy = '''{
    admin off
    servers {
        protocols h1 h2
    }
}
voice.zrzur.com {
    reverse_proxy 127.0.0.1:7880
}
'''
for name, text in [('livekit.yaml', livekit), ('compose.yml', compose), ('Caddyfile', proxy)]:
    path = ROOT / name
    if path.exists() and path.read_text() != text:
        raise SystemExit(f'Existing {name} differs; review before replacement.')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(text)
subprocess.run(['docker', 'compose', 'config', '--quiet'], cwd=ROOT, check=True)
print('Voice configuration validated; credentials retained only in protected files on this server.')
