#!/usr/bin/env bash
# Instal·lació inicial a Ubuntu 24.04 (Oracle A1, ARM64). Executa-ho una vegada.
set -euo pipefail
cd "$(dirname "$0")/.."
sudo timedatectl set-timezone Europe/Madrid
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps chromium
mkdir -p state logs
[ -f .env ] || cp .env.example .env
echo "Fet. Ara edita .env (nano .env) i prova: .venv/bin/python -m bot.selftest"
