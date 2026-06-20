#!/usr/bin/env bash
set -euo pipefail

echo "=== Installing Python dependencies ==="
python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

mkdir -p data app/static/media

echo "=== Starting app on port ${PORT:-3001} ==="
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-3001}"
