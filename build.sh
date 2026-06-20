#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing pip ==="
python3 -m ensurepip --upgrade 2>/dev/null \
  || { curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python3 /tmp/get-pip.py --user; }

export PATH="$HOME/.local/bin:$PATH"

echo "=== Installing Python dependencies ==="
python3 -m pip install --no-cache-dir --user -r requirements.txt

mkdir -p data app/static/media
echo "=== Build complete ==="
