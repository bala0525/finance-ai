# Deployment notes

Architecture: React SPA (static build) -> FastAPI backend -> Supabase PostgreSQL.
No hosting provider is assumed.

## Backend
1. `pip install -r requirements.txt`
2. Set environment variables (see `.env.example`). With `APP_ENV=production` the app
   refuses to start unless `SECRET_KEY` is 32+ random chars, `FRONTEND_URL` is not
   localhost, `DATABASE_URL` is not localhost and `DEBUG` is false.
3. `alembic upgrade head` (creates all tables and enables Row Level Security).
4. Start: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT`
5. Health check: `GET /health`.

| Variable | Required | Purpose |
|---|---|---|
| DATABASE_URL | yes | Supabase Postgres URI (`?sslmode=require`) |
| SECRET_KEY | yes | JWT signing key |
| APP_ENV | no | `production` enables startup checks, hides `/docs` |
| FRONTEND_URL / CORS_ORIGINS | yes / no | Allowed browser origins |
| SUPABASE_URL | yes | `https://<ref>.supabase.co` |
| SUPABASE_SERVICE_ROLE_KEY | yes | Backend-only key for Storage. Never expose to the frontend |
| SUPABASE_STORAGE_BUCKET | yes | Private bucket for documents + reports (see `supabase/storage.sql`) |
| SUPABASE_ANON_KEY | no | Kept for completeness; the backend does not use it |
| CORS_ORIGINS, DB_POOL_SIZE, DB_MAX_OVERFLOW, DOCS_ENABLED, STORAGE_TIMEOUT_SECONDS | no | Optional overrides (defaults in `app/core/config.py`) |
| GEMINI_API_KEY | for AI features | Extraction, classification, Analyst |
| ACCESS_TOKEN_EXPIRE_MINUTES, MANAGER_APPROVAL_LIMIT, DB_POOL_SIZE | no | Tuning |

## Frontend
Build-time variable `REACT_APP_API_BASE_URL` = deployed backend URL (the production
build fails fast if it is missing). `npm run build`, publish `build/`, and configure the
host to serve `index.html` for unknown paths (client-side routing).
Never put secrets or Supabase keys in `REACT_APP_*` variables.

## Supabase / RLS
- The app uses its own JWT login, not Supabase Auth, and connects as the database
  owner, which bypasses RLS. RLS is enabled on every table with no policies, so
  Supabase's public REST/GraphQL endpoints expose nothing. Per-user access is enforced
  in the API (all profile/settings endpoints act only on the authenticated user).
- After adding tables outside Alembic, run `supabase/rls.sql` in the SQL editor.

## Known limitations
- (Resolved) Uploaded documents and generated reports live only in Supabase Storage;
  the server needs no persistent disk. Rows created before the migration need
  `python -m scripts.migrate_local_uploads_to_supabase --source-dir <old uploads>`.
- Notification preferences are stored but no email service is configured.
- Changing a password does not revoke tokens already issued.

---
# AWS: Amplify (frontend) + Elastic Beanstalk or EC2 (backend)

## Rules that apply to both backend options
- **HTTPS is mandatory.** Amplify serves the site over HTTPS, and browsers block calls to an
  `http://` API (mixed content). The backend needs a domain + TLS certificate
  (e.g. `api.your-domain.com`).
- **Supabase from AWS:** use the Supabase *session pooler* connection string (direct
  connections are IPv6-only on some plans, which EC2/EB do not use by default). Keep `?sslmode=require`.
- Never commit `.env`. Set variables in the EB console (Configuration > Environment properties)
  or in `/etc/azentmart/api.env` on EC2:
  `APP_ENV=production`, `DEBUG=false`, `SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`,
  `FRONTEND_URL=https://<your Amplify domain>`, `CORS_ORIGINS=<extra Amplify branch URLs>`.

## Frontend on Amplify
1. Connect the repo; `amplify.yml` (in the Frontend folder) is picked up automatically.
2. App settings > Environment variables: `REACT_APP_API_BASE_URL=https://api.your-domain.com`.
3. App settings > Rewrites and redirects: add a rule
   Source `</^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>`,
   Target `/index.html`, Type `200 (Rewrite)`. Without it, refreshing `/profile` returns 404.
4. Redeploy after changing any variable (they are baked in at build time).

## Backend on Elastic Beanstalk
Included: `Procfile` (gunicorn), `.ebextensions/01_migrate.config` (runs `alembic upgrade head`),
`.platform/nginx/conf.d/proxy.conf` (25 MB uploads).
1. Create a **load-balanced** environment on a Python platform (health check path `/health`).
   Pick a Python version EB supports; adjust if a pinned package needs a different one.
2. Add an HTTPS (443) listener to the load balancer with an ACM certificate, and point
   `api.your-domain.com` at it.
3. Zip the backend folder contents (without `.venv` and `.env`) and deploy.
4. **File storage:** files live in Supabase Storage, so ephemeral EB disks and
   scale-out are safe. Set the three `SUPABASE_*` variables in the EB console.

## Backend on EC2
1. Ubuntu instance; security group: 80/443 open, 22 from your IP only.
2. `sudo apt install python3-venv nginx certbot python3-certbot-nginx`
3. Copy the backend to `/opt/azentmart/backend`, then create the venv and
   `pip install -r requirements.txt`.
4. `sudo mkdir -p /etc/azentmart`; put variables in `/etc/azentmart/api.env`
   (including the `SUPABASE_*` values), and `chmod 600` it.
5. `cd /opt/azentmart/backend && set -a && . /etc/azentmart/api.env && set +a && .venv/bin/alembic upgrade head`
6. Install `deploy-ec2/azentmart-api.service` into `/etc/systemd/system/`, then
   `sudo systemctl enable --now azentmart-api`.
7. Install `deploy-ec2/nginx-api.conf` into `/etc/nginx/sites-available/`, enable it,
   edit `server_name`, then `sudo certbot --nginx -d api.your-domain.com`.
8. Nothing to back up on disk; back up via Supabase (database + Storage).

## Supabase Storage setup
1. Run `supabase/storage.sql` in the SQL editor (or `python -m scripts.check_storage`,
   which creates the private bucket automatically).
2. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`.
3. `alembic upgrade head` (adds `storage_bucket` / `storage_path` columns).
4. `python -m scripts.check_storage` must print `PASS`.
5. Legacy files: `python -m scripts.migrate_local_uploads_to_supabase --source-dir <old uploads> --dry-run`, then without `--dry-run`.


## Release note: AI employee workflows

This release adds migration `e5a1c7b9d3f2` (new tables + document confidence/coding columns). Run `alembic upgrade head` before starting the new code (the EB `.ebextensions` migrate hook and the systemd `ExecStartPre` already do this). Take a database backup first. See `WORKFLOWS.md` for the endpoints. `CORS_ORIGINS` (optional, comma separated) now works as described above.
