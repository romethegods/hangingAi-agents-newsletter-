# Deploying HangingAi

The code has no host-specific logic: everything is Docker images + environment
variables. That's what makes the Railway → Google Cloud move a config change.

## Phase 1: Railway (backend) + Vercel (frontend)

1. **Postgres**: add Railway's Postgres (pgvector template once we reach M2).
2. **API service**: from this repo, root directory `backend`, Dockerfile path `backend/Dockerfile`.
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (the app converts `postgresql://` itself)
   - `CORS_ORIGINS` = `["https://hangingai.com","https://www.hangingai.com"]`
   - Health check path: `/health`. Migrations run automatically on boot.
3. **Worker service**: same repo, Dockerfile path `backend/Dockerfile.worker`, same `DATABASE_URL`.
   No public port. Give it ≥1 GB RAM (Chrome).
4. **Frontend**: Vercel project with root directory `frontend/`. Env: `API_URL=https://api.hangingai.com`,
   `SITE_URL=https://hangingai.com`. The site calls the API server-side only, so the API's CORS list
   doesn't need the Vercel domain.
5. **DNS**: `hangingai.com` → Vercel, `api.hangingai.com` → Railway API service.

## Phase 2: Google Cloud VM

`docker-compose.yml` runs the whole backend on one VM.

1. Create a Compute Engine VM (e2-medium is plenty to start; Debian 12), open ports 80/443.
2. Install Docker, clone the repo, create `.env` from `.env.example` (set a strong `POSTGRES_PASSWORD`).
3. Move data: `pg_dump "$RAILWAY_DATABASE_URL" | docker compose exec -T db psql -U hanging hanging`
4. `docker compose up -d --build`
5. Put Caddy (automatic HTTPS) in front of the API:
   ```
   api.hangingai.com {
       reverse_proxy localhost:8000
   }
   ```
6. Point `api.hangingai.com` at the VM's static IP. The frontend can stay on Vercel or move later.
7. Back up the `pgdata` volume, e.g. a nightly `pg_dump` to a Cloud Storage bucket.

If the database outgrows the VM, switch `DATABASE_URL` to Cloud SQL. No code changes needed.
