#!/usr/bin/env bash
set -euo pipefail

echo "=== Creating venv ==="
python3 -m venv .venv
source .venv/bin/activate

echo "=== Installing Python dependencies ==="
pip install --no-cache-dir -r requirements.txt

mkdir -p data app/static/media
echo "=== Build complete ==="
