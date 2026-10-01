#!/usr/bin/env bash
# Deploy the latest main: pull, rebuild, restart changed services. Run on the VM:
#   sudo bash /opt/hangingai/deploy/deploy.sh
set -euo pipefail
cd /opt/hangingai
[ -f .env ] || { echo "missing /opt/hangingai/.env (copy .env.example and fill it in)"; exit 1; }
git fetch --quiet origin
git reset --hard origin/main  # the VM never has local edits; config lives in .env
docker compose build --pull
docker compose up -d --remove-orphans  # the API runs migrations on boot
docker image prune -f >/dev/null
docker compose ps
