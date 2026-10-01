#!/usr/bin/env bash
# Nightly Postgres backup: a compressed dump kept 14 days on the VM, and copied to
# Google Cloud Storage when BACKUP_BUCKET is set in .env (e.g. gs://hangingai-backups).
set -euo pipefail
cd /opt/hangingai
BACKUP_BUCKET=$(grep -E '^BACKUP_BUCKET=' .env | cut -d= -f2- || true)
dir=/var/backups/hangingai
mkdir -p "$dir"
file="$dir/hangingai-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T db pg_dump -U hanging --no-owner hanging | gzip -9 > "$file"
[ -s "$file" ] || { echo "backup is empty"; rm -f "$file"; exit 1; }
find "$dir" -name 'hangingai-*.sql.gz' -mtime +14 -delete
if [ -n "${BACKUP_BUCKET:-}" ]; then
  gcloud storage cp "$file" "$BACKUP_BUCKET/" --quiet
fi
echo "$(date -u) backup ok: $file ($(du -h "$file" | cut -f1))"
