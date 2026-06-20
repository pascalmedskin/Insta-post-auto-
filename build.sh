#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing pip ==="
curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python3 /tmp/get-pip.py --break-system-packages

echo "=== Installing Python dependencies ==="
python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

mkdir -p data app/static/media
echo "=== Build complete ==="
