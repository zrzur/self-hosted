#!/usr/bin/env bash
# Prepare a fresh Ubuntu 24.04 main server: swap, Docker, and this repository.
# Idempotent. Builds nothing and starts no Zrzur service.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Swap keeps a memory spike from freezing the whole host (main locked up without it).
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 git python3 openssl
systemctl enable --now docker

# Older hosts used /opt/zrzur/infrastructure; keep updating that checkout if it exists.
if [ -d /opt/zrzur/infrastructure/.git ]; then
  git -C /opt/zrzur/infrastructure remote set-url origin https://github.com/zrzur/self-hosted
  git -C /opt/zrzur/infrastructure pull --ff-only
elif [ -d /opt/zrzur/self-hosted/.git ]; then
  git -C /opt/zrzur/self-hosted pull --ff-only
else
  mkdir -p /opt/zrzur
  git clone https://github.com/zrzur/self-hosted /opt/zrzur/self-hosted
fi
chmod 700 /opt/zrzur

echo "Host ready: $(docker --version); $(docker compose version); swap $(swapon --show=SIZE --noheadings | head -1)"
