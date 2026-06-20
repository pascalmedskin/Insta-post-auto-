#!/usr/bin/env bash
set -euo pipefail

echo "Installing Python dependencies..."
python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

mkdir -p data app/static/media
echo "Build complete"
