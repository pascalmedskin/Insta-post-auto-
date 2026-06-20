#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y --no-install-recommends python3 python3-pip python3-venv libcairo2 fonts-dejavu-core

# Symlink so "pip" exists in PATH (DollarDeploy calls bare "pip")
ln -sf /usr/bin/pip3 /usr/local/bin/pip 2>/dev/null || true
ln -sf /usr/bin/python3 /usr/local/bin/python 2>/dev/null || true

pip3 install --no-cache-dir --break-system-packages -r requirements.txt

mkdir -p data app/static/media
