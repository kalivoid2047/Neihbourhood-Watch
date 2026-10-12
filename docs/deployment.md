# Deployment Notes

## Docker Compose Baseline

The included Docker Compose stack runs:

- Django API
- PostgreSQL with PostGIS
- Redis
- MinIO
- Nginx

```powershell
docker compose up --build
```

## Environment

Copy `.env.example` to `.env` and change secrets before production use.

Required production settings:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `REDIS_URL`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`

## Deployment Targets

The same container shape can be deployed to AWS, Azure, DigitalOcean, or an Ubuntu VPS. Production deployments should place TLS termination in front of Nginx or configure Nginx with certificates directly.

## Phase 1 Verification

```powershell
python backend/manage.py check --settings=config.settings.local
python backend/manage.py test apps --settings=config.settings.test
```
