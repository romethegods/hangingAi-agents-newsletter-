#!/usr/bin/env bash
# One-time setup of a fresh Debian/Ubuntu VM for HangingAi. Run as root:
#   sudo bash deploy/vm-setup.sh
set -euo pipefail

echo "== packages, Docker (official repo), automatic security updates"
apt-get update
apt-get install -y ca-certificates curl git gnupg unattended-upgrades
install -m 0755 -d /etc/apt/keyrings
. /etc/os-release
curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== 2 GB swap (Next.js builds and Chrome spike memory)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo "== app checkout in /opt/hangingai"
if [ ! -d /opt/hangingai/.git ]; then
  git clone https://github.com/romethegods/hangingAi-agents-newsletter-.git /opt/hangingai
fi

echo "== nightly database backup at 03:30"
install -m 0755 /opt/hangingai/deploy/backup.sh /usr/local/bin/hangingai-backup
echo "30 3 * * * root /usr/local/bin/hangingai-backup >> /var/log/hangingai-backup.log 2>&1" > /etc/cron.d/hangingai-backup

echo "Done. Next: create /opt/hangingai/.env (see .env.example), then run deploy/deploy.sh"
