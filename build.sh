#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing pip ==="
python3 -m ensurepip --upgrade --break-system-packages

echo "=== Installing Python dependencies ==="
python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

mkdir -p data app/static/media
echo "=== Build complete ==="
