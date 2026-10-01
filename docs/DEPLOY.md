# Deploying HangingAi

Everything runs on one Google Cloud VM with Docker Compose:

```
internet ─443─▶ caddy (HTTPS, Let's Encrypt) ─┬─ /api/*  ▶ api (FastAPI, runs migrations on boot)
                                              └─ /*      ▶ web (Next.js)  ─▶ api
                worker (scraper, README demos, releases, daily briefs) ─▶ db (Postgres 16)
```

Only Caddy is reachable from the internet (ports 80/443). The API listens on the
Docker network (and on the VM's localhost for debugging).

## 1. VM (once)

- Compute Engine VM: **e2-medium** (2 vCPU, 4 GB) is enough to start; Debian 12;
  30 GB balanced disk; a **static external IP**; firewall: allow tcp 80, 443 (and udp 443).
- SSH in and run: `sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/romethegods/hangingAi-agents-newsletter-/main/deploy/vm-setup.sh)"`
  (installs Docker, automatic security updates, 2 GB swap, the app in `/opt/hangingai`,
  and a nightly backup cron).

## 2. Configuration

`sudo cp /opt/hangingai/.env.example /opt/hangingai/.env` and fill in at least:
`SITE_DOMAIN`, `SITE_URL`, `ACME_EMAIL`, `POSTGRES_PASSWORD`, `SECRET_KEY`,
`NEXT_SERVER_ACTIONS_ENCRYPTION_KEY`, `ADMIN_EMAILS`, and for email `EMAIL_BACKEND=smtp`
plus the `SMTP_*` values. `chmod 600 .env`; it holds secrets and never goes in git.

## 3. DNS

At the registrar: `A @ → <static IP>` and `A www → <static IP>` (or `CNAME www → @`).
Caddy requests certificates automatically once DNS points at the VM.

## 4. Deploy

`sudo bash /opt/hangingai/deploy/deploy.sh` (pull `main`, rebuild, restart; migrations
run automatically). Run it again for every update.

## 5. Operations

- Logs: `cd /opt/hangingai && sudo docker compose logs -f api` (or web, worker, caddy).
  Docker rotates them (10 MB × 5 per service).
- Backups: nightly `pg_dump` at 03:30 UTC to `/var/backups/hangingai` (14 days), and to
  `BACKUP_BUCKET` in Cloud Storage when set. Restore:
  `gunzip -c backup.sql.gz | sudo docker compose exec -T db psql -U hanging hanging`.
- Health: `https://<domain>/health`.
- Turning on the Arena: add `ANTHROPIC_API_KEY` and/or `HF_TOKEN` to `.env`, then
  `sudo docker compose up -d api` (no rebuild needed).
