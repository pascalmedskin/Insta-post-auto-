#!/usr/bin/env bash
# Lance Insta Post Auto en local, accessible depuis ton iPhone (même Wi-Fi).
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
PY="${PYTHON:-python3}"

# 1. Environnement virtuel + dépendances
if [ ! -d ".venv" ]; then
  echo "📦 Création de l'environnement virtuel…"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "📦 Installation des dépendances…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 2. Fichier .env (mode démo si absent)
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "ℹ️  .env créé (mode démo). Ajoute tes clés API quand tu veux."
fi

# 3. Détection de l'IP locale (Mac puis Linux)
LAN_IP=""
if command -v ipconfig >/dev/null 2>&1; then
  LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [ -z "$LAN_IP" ] && command -v hostname >/dev/null 2>&1; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi
[ -z "$LAN_IP" ] && LAN_IP="<IP-de-ton-ordi>"

echo ""
echo "============================================================"
echo "  📸 Insta Post Auto démarre…"
echo "  💻 Sur cet ordi      : http://localhost:${PORT}"
echo "  📱 Sur ton iPhone    : http://${LAN_IP}:${PORT}"
echo "     (iPhone sur le MÊME Wi-Fi)"
echo "============================================================"
echo ""

# 4. Cairo lib pour conversion SVG (logos) si installé via Homebrew
for _dir in /opt/homebrew/lib /usr/local/lib; do
  [ -f "$_dir/libcairo.2.dylib" ] && export DYLD_LIBRARY_PATH="${_dir}:${DYLD_LIBRARY_PATH:-}" && break
done

# 5. Lancement accessible sur le réseau local
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
