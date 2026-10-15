# Neighbourhood Watch Zimbabwe — Deployment Guide

This guide covers running NHWZ without Docker, using native Python virtual
environments on Linux, macOS, and Windows.

Docker remains a fully supported option; see `docker-compose.yml` and
`infra/docker/` for that path.  The two approaches are independent — you can
use Docker for local development and native Python for production, or vice-versa.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project layout](#2-project-layout)
3. [Quick-start (any OS)](#3-quick-start-any-os)
4. [Linux / macOS](#4-linux--macos)
   - 4.1 Development
   - 4.2 Production (systemd)
   - 4.3 Production (gunicorn + nginx)
5. [Windows](#5-windows)
   - 5.1 Development
   - 5.2 Production (waitress + NSSM)
   - 5.3 WebSocket support on Windows
6. [Environment variables reference](#6-environment-variables-reference)
7. [Database setup](#7-database-setup)
8. [Redis setup](#8-redis-setup)
9. [Frontend build](#9-frontend-build)
10. [PaaS deployment (Heroku / Render / Railway)](#10-paas-deployment)
11. [Kubernetes](#11-kubernetes)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

### All platforms

| Dependency | Version | Notes |
|------------|---------|-------|
| Python | 3.12+ | 3.11 works but 3.12 is tested |
| Node.js | 18+ | 20 LTS recommended |
| npm | 9+ | bundled with Node |
| PostgreSQL | 14–16 | PostGIS optional (activates geo features) |
| Redis | 6–7 | Required for Celery and WebSocket channel layer |

### Linux-only packages

```bash
# Ubuntu / Debian
sudo apt-get install -y \
    python3-dev python3-venv \
    libpq-dev build-essential \
    libmagic1 \
    postgresql-client redis-tools

# Fedora / RHEL
sudo dnf install -y python3-devel postgresql-devel libmagic
```

### macOS

```bash
brew install python@3.12 postgresql redis libmagic
```

### Windows

- Python 3.12 from [python.org](https://www.python.org/downloads/) — check "Add to PATH"
- Node.js 20 LTS from [nodejs.org](https://nodejs.org/)
- PostgreSQL 16 from [postgresql.org](https://www.postgresql.org/download/windows/)
- Redis: use [Redis for Windows](https://github.com/microsoftarchive/redis/releases)
  or install via WSL (`wsl --install` then `sudo apt install redis-server`)

> **python-magic on Windows**: `python-magic` needs `libmagic.dll`.
> Download from [github.com/pidydx/libmagicwin64](https://github.com/pidydx/libmagicwin64)
> and place `magic.mgc` + `libmagic.dll` in your `System32` or alongside the Python exe.
> Alternatively, install `python-magic-bin` instead of `python-magic`.

---

## 2. Project layout

```
/
├── backend/               Django project root (manage.py is here)
│   ├── config/            settings/, wsgi.py, asgi.py, celery.py, urls.py
│   └── apps/              Django applications
├── frontend/              React + Vite SPA
├── requirements/
│   ├── base.txt           Core runtime dependencies
│   ├── prod.txt           base + gunicorn + sentry (Linux/macOS prod)
│   ├── dev.txt            base + pytest + flake8
│   └── windows.txt        base + waitress + sentry (Windows prod)
├── requirements.txt       Full union — used by CI and Docker
├── runtime.txt            python-3.12  (PaaS hint)
├── Procfile               web / worker / beat processes (PaaS / Foreman)
├── scripts/
│   ├── setup.sh           Linux/macOS first-time setup
│   ├── setup.bat          Windows CMD first-time setup
│   ├── setup.ps1          Windows PowerShell first-time setup
│   ├── start-dev.sh       Linux/macOS: start all dev services
│   ├── start-dev.bat      Windows CMD dev start
│   ├── start-dev.ps1      Windows PowerShell dev start
│   ├── start-prod.sh      Linux/macOS: start all production services
│   ├── start-prod.bat     Windows CMD production start
│   └── start-prod.ps1     Windows PowerShell production start
├── .env.example           Template — copy to .env
├── Makefile               Convenience targets
├── docker-compose.yml     Docker path (still supported)
└── k8s/                   Kubernetes manifests
```

---

## 3. Quick-start (any OS)

```bash
# 1. Clone
git clone <repo-url> nhwz
cd nhwz

# 2. Copy and edit environment
cp .env.example .env
# At minimum set: DJANGO_SECRET_KEY, DATABASE_URL, REDIS_URL

# 3. Run setup
# Linux / macOS:
bash scripts/setup.sh

# Windows PowerShell:
.\scripts\setup.ps1

# Windows CMD:
scripts\setup.bat

# 4. Start development services
# Linux / macOS:
bash scripts/start-dev.sh

# Windows PowerShell:
.\scripts\start-dev.ps1

# Windows CMD:
scripts\start-dev.bat
```

The API will be available at **http://localhost:8000** and the frontend dev
server at **http://localhost:5173**.

---

## 4. Linux / macOS

### 4.1 Development

```bash
# First-time setup
bash scripts/setup.sh

# Daily start (Django + Celery + Vite, all in one terminal)
bash scripts/start-dev.sh

# Or use Make targets
make setup
make dev
```

The `start-dev.sh` script starts four background processes and traps `Ctrl-C`
to kill all of them cleanly.

### 4.2 Production (systemd)

Systemd is the recommended way to run NHWZ as an always-on service on Linux.
Create one unit file per process.

**1. Create system user**

```bash
sudo useradd --system --shell /bin/false nhwz
sudo mkdir -p /opt/nhwz
sudo chown nhwz:nhwz /opt/nhwz
```

**2. Clone and set up**

```bash
sudo -u nhwz git clone <repo-url> /opt/nhwz/app
cd /opt/nhwz/app
sudo -u nhwz bash -c "MODE=prod bash scripts/setup.sh"
# Edit /opt/nhwz/app/.env with production values
```

**3. Systemd unit files**

`/etc/systemd/system/nhwz-api.service`:
```ini
[Unit]
Description=NHWZ API (daphne ASGI)
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=nhwz
WorkingDirectory=/opt/nhwz/app/backend
EnvironmentFile=/opt/nhwz/app/.env
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/opt/nhwz/app/.venv/bin/daphne \
    -b 127.0.0.1 -p 8000 config.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/nhwz-worker.service`:
```ini
[Unit]
Description=NHWZ Celery Worker
After=network.target redis.service nhwz-api.service

[Service]
Type=simple
User=nhwz
WorkingDirectory=/opt/nhwz/app/backend
EnvironmentFile=/opt/nhwz/app/.env
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/opt/nhwz/app/.venv/bin/celery \
    -A config.celery worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/nhwz-beat.service`:
```ini
[Unit]
Description=NHWZ Celery Beat
After=network.target redis.service nhwz-worker.service

[Service]
Type=simple
User=nhwz
WorkingDirectory=/opt/nhwz/app/backend
EnvironmentFile=/opt/nhwz/app/.env
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/opt/nhwz/app/.venv/bin/celery \
    -A config.celery beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**4. Enable and start**

```bash
sudo systemctl daemon-reload
sudo systemctl enable nhwz-api nhwz-worker nhwz-beat
sudo systemctl start  nhwz-api nhwz-worker nhwz-beat
sudo systemctl status nhwz-api
```

### 4.3 Production (nginx reverse proxy)

Install nginx, then create `/etc/nginx/sites-available/nhwz`:

```nginx
upstream nhwz_api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name example.com;

    client_max_body_size 110m;

    # Serve React build output
    location / {
        root /opt/nhwz/app/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to daphne
    location /api/ {
        proxy_pass http://nhwz_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket upgrade
    location /ws/ {
        proxy_pass http://nhwz_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }

    # Django admin and static files
    location /static/ {
        alias /opt/nhwz/app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/nhwz /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

For HTTPS, add Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d example.com
```

---

## 5. Windows

### 5.1 Development

```powershell
# PowerShell (recommended)
.\scripts\setup.ps1
.\scripts\start-dev.ps1
```

```cmd
REM Command Prompt
scripts\setup.bat
scripts\start-dev.bat
```

`start-dev.ps1` opens each service in its own titled cmd window:
- **NHWZ-Django** — `python manage.py runserver`
- **NHWZ-Celery-Worker** — Celery with `--pool=solo` (required on Windows)
- **NHWZ-Celery-Beat** — Celery beat
- **NHWZ-Frontend** — Vite dev server

> **Celery `--pool=solo`**: the default `prefork` pool uses `os.fork()`, which
> is not available on Windows.  `--pool=solo` runs tasks synchronously in the
> main process — adequate for development but not for production.

### 5.2 Production (waitress + NSSM)

`waitress` is a pure-Python WSGI server that works natively on Windows without
any C extensions.

```powershell
.\scripts\setup.ps1 -Mode prod
.\scripts\start-prod.ps1
```

**Running as Windows Services with NSSM**

[NSSM](https://nssm.cc/) wraps any executable as a Windows Service.

```cmd
REM Download nssm.exe and place it on PATH, then:

nssm install NHWZ-API "C:\nhwz\.venv\Scripts\waitress-serve.exe"
nssm set NHWZ-API AppParameters "--port=8000 --threads=8 config.wsgi:application"
nssm set NHWZ-API AppDirectory  "C:\nhwz\backend"
nssm set NHWZ-API AppEnvironmentExtra "DJANGO_SETTINGS_MODULE=config.settings.production"
nssm set NHWZ-API Start SERVICE_AUTO_START
nssm start NHWZ-API

nssm install NHWZ-Worker "C:\nhwz\.venv\Scripts\celery.exe"
nssm set NHWZ-Worker AppParameters "-A config.celery worker --loglevel=info --pool=solo"
nssm set NHWZ-Worker AppDirectory  "C:\nhwz\backend"
nssm set NHWZ-Worker AppEnvironmentExtra "DJANGO_SETTINGS_MODULE=config.settings.production"
nssm set NHWZ-Worker Start SERVICE_AUTO_START
nssm start NHWZ-Worker

nssm install NHWZ-Beat "C:\nhwz\.venv\Scripts\celery.exe"
nssm set NHWZ-Beat AppParameters "-A config.celery beat --loglevel=info"
nssm set NHWZ-Beat AppDirectory   "C:\nhwz\backend"
nssm set NHWZ-Beat AppEnvironmentExtra "DJANGO_SETTINGS_MODULE=config.settings.production"
nssm set NHWZ-Beat Start SERVICE_AUTO_START
nssm start NHWZ-Beat
```

### 5.3 WebSocket support on Windows

`waitress` is WSGI-only and cannot handle WebSocket connections (`/ws/`).

Options:
1. **daphne** (bundled with `channels[daphne]` — already installed):
   Run daphne on a separate port (e.g., 8001) and route `/ws/` to it via nginx
   (using nginx for Windows or IIS with ARR).

2. **Run daphne as the sole server**:
   ```powershell
   .\.venv\Scripts\daphne.exe -b 0.0.0.0 -p 8000 config.asgi:application
   ```
   daphne handles both HTTP and WebSocket on the same port. Replace the
   `waitress-serve` command in the NSSM setup above.

---

## 6. Environment variables reference

All variables are read from `.env` (loaded by the startup scripts) or from
the process environment.  Required variables have no default.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | **Yes (prod)** | `local-dev-key` | Django secret key — generate a 50+ char random value |
| `DATABASE_URL` | **Yes** | SQLite | PostgreSQL DSN: `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis DSN for cache, Celery, Channels |
| `DJANGO_ALLOWED_HOSTS` | Yes | `localhost,127.0.0.1` | Comma-separated hostnames |
| `DJANGO_DEBUG` | No | `False` | Never `True` in production |
| `DJANGO_SETTINGS_MODULE` | No | `config.settings.local` | Override at process level |
| `CORS_ALLOWED_ORIGINS` | No | `[]` | Comma-separated origins for CORS |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | No | `[]` | Comma-separated origins for CSRF |
| `USE_S3_STORAGE` | No | `False` | Route media through MinIO/S3 |
| `MINIO_ENDPOINT_URL` | If S3 | — | MinIO endpoint URL |
| `MINIO_ACCESS_KEY` | If S3 | — | MinIO access key |
| `MINIO_SECRET_KEY` | If S3 | — | MinIO secret key |
| `MINIO_BUCKET_NAME` | If S3 | `nhwz-media` | Bucket name |
| `EMAIL_HOST` | No | `localhost` | SMTP host |
| `EMAIL_PORT` | No | `587` | SMTP port |
| `EMAIL_USE_TLS` | No | `True` | Use STARTTLS |
| `EMAIL_HOST_USER` | No | `""` | SMTP username |
| `EMAIL_HOST_PASSWORD` | No | `""` | SMTP password |
| `DEFAULT_FROM_EMAIL` | No | `noreply@nhwz.example.com` | From address |
| `SENTRY_DSN` | No | `""` | Activates Sentry when set |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `APP_VERSION` | No | `8.0.0` | Shown in `/api/health/` and Sentry |
| `OTP_EXPOSE_DEBUG_CODES` | No | `False` | Return OTP code in API response |
| `OTP_TTL_MINUTES` | No | `10` | OTP expiry |
| `OTP_MAX_ATTEMPTS` | No | `5` | Max wrong attempts before lockout |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime |
| `PORT` | No | `8000` | HTTP port (used by Procfile / start-prod.sh) |
| `WORKERS` | No | `4` | Celery worker concurrency |

---

## 7. Database setup

### PostgreSQL (recommended for production)

```bash
# Create database and user
psql -U postgres -c "CREATE USER nhwz WITH PASSWORD 'your-password';"
psql -U postgres -c "CREATE DATABASE nhwz OWNER nhwz;"
```

Set in `.env`:
```
DATABASE_URL=postgresql://nhwz:your-password@localhost:5432/nhwz
```

Then run migrations:
```bash
# Linux/macOS
source .venv/bin/activate
cd backend && python manage.py migrate --settings=config.settings.production

# Windows
.venv\Scripts\python.exe backend\manage.py migrate --settings=config.settings.production
```

### SQLite (development / quick testing only)

Leave `DATABASE_URL` unset. Django will create `db.sqlite3` at the project root.

> SQLite does not support PostGIS — geospatial and proximity queries will be
> served by the pure-Python Haversine fallback built into the project.

---

## 8. Redis setup

### Linux

```bash
sudo apt install redis-server   # Ubuntu/Debian
sudo systemctl enable --now redis
redis-cli ping                  # → PONG
```

### macOS

```bash
brew install redis
brew services start redis
```

### Windows

**Option A — WSL (recommended)**
```powershell
wsl --install       # one-time
wsl
sudo apt install redis-server
sudo service redis-server start
```
Then set `REDIS_URL=redis://localhost:6379/0` — WSL Redis is reachable from Windows localhost.

**Option B — Native Redis for Windows**
Download from [github.com/microsoftarchive/redis](https://github.com/microsoftarchive/redis/releases)
and run `redis-server.exe`.

---

## 9. Frontend build

The frontend is a React + Vite SPA served as static files in production.

```bash
# Install dependencies
cd frontend && npm ci

# Production build (outputs to frontend/dist/)
npm run build
```

In production, serve `frontend/dist/` with nginx (Linux/macOS) or IIS / a simple
static file server (Windows):
```bash
# Quick static file server for testing (Python)
cd frontend/dist && python -m http.server 3000
```

For development, the Vite dev server proxies API requests:
```bash
cd frontend && npm run dev   # http://localhost:5173
```

---

## 10. PaaS deployment

The project ships a `Procfile` and `runtime.txt` for Heroku-compatible platforms
(Heroku, Render, Railway, Fly.io).

### Heroku

```bash
heroku create nhwz-app
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
heroku config:set \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" \
    DJANGO_ALLOWED_HOSTS="nhwz-app.herokuapp.com" \
    CORS_ALLOWED_ORIGINS="https://nhwz-app.herokuapp.com"

# The DATABASE_URL and REDIS_URL are set automatically by the add-ons.
git push heroku main
heroku run "cd backend && python manage.py migrate --settings=config.settings.production"
heroku run "cd backend && python manage.py seed_roles --settings=config.settings.production"
```

The `Procfile` starts three dynos: `web` (daphne), `worker` (Celery), `beat` (Celery Beat).

### Render / Railway

Set the same environment variables as above.  Point the build command to
`pip install -r requirements/prod.txt` and the start command to the `web`
line from the `Procfile`.

---

## 11. Kubernetes

See `k8s/` for full manifests.  Quick deploy:

```bash
# Apply namespace first
kubectl apply -f k8s/namespace.yaml

# Edit secrets (replace all CHANGE_ME values)
vim k8s/secrets.yaml

# Apply everything
kubectl apply -f k8s/

# Run migrations as a one-off Job
kubectl exec -n nhwz deploy/nhwz-api -- \
    python manage.py migrate --settings=config.settings.production
```

---

## 12. Troubleshooting

### `ModuleNotFoundError: No module named 'django'`

The virtual environment is not activated or the wrong Python is being used.

```bash
# Linux/macOS
source .venv/bin/activate
which python   # should point to .venv/bin/python

# Windows
.venv\Scripts\activate
where python   # should point to .venv\Scripts\python.exe
```

### `django.db.utils.OperationalError: could not connect to server`

PostgreSQL is not running or `DATABASE_URL` is wrong.

```bash
# Test connection
psql "$DATABASE_URL" -c "SELECT 1;"
```

### `redis.exceptions.ConnectionError`

Redis is not running.

```bash
redis-cli ping   # should return PONG
```

### Celery tasks not running

1. Check worker is started: `celery -A config.celery inspect active`
2. Verify `REDIS_URL` is the same in the Django process and the worker.
3. On Windows: confirm `--pool=solo` is passed to the worker.

### `MIME type mismatch` on media upload

`python-magic` requires the native `libmagic` library.

- **Linux**: `sudo apt install libmagic1`
- **macOS**: `brew install libmagic`
- **Windows**: install `python-magic-bin` and add the `magic.mgc` path.

If `libmagic` cannot be installed, the check is silently skipped (MIME
validation falls through).

### Static files returning 404 after deploy

Run `collectstatic` and confirm nginx / IIS serves from the correct path:

```bash
python backend/manage.py collectstatic --noinput \
    --settings=config.settings.production
```

### `DJANGO_SECRET_KEY` error on startup

Generate a valid key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the output into `.env` as `DJANGO_SECRET_KEY=<value>`.

### WebSocket connections fail on Windows (waitress)

`waitress` is WSGI-only.  Switch to `daphne`:

```powershell
.\.venv\Scripts\daphne.exe -b 0.0.0.0 -p 8000 config.asgi:application
```

---

*End of deployment guide — NHWZ v8.0.0*
