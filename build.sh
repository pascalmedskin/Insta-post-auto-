#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing pip ==="
apt-get update -qq && apt-get install -y --no-install-recommends python3-pip python3-venv libcairo2 2>/dev/null || python3 -m ensurepip --upgrade 2>/dev/null || true

echo "=== Installing Python dependencies ==="
python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt 2>/dev/null \
  || pip3 install --no-cache-dir -r requirements.txt 2>/dev/null \
  || python3 -m pip install --no-cache-dir -r requirements.txt

mkdir -p data app/static/media
echo "=== Build complete ==="
