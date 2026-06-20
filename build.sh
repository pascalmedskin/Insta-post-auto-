#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y --no-install-recommends python3 python3-pip python3-venv libcairo2 fonts-dejavu-core

python3 -m venv /home/ubuntu/venv
source /home/ubuntu/venv/bin/activate

pip install --no-cache-dir -r requirements.txt

mkdir -p data app/static/media
