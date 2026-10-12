# Quick Start Guide

Get Neighbourhood Watch Zimbabwe running in 5 minutes!

## For the Impatient 🚀

### Option 1: Docker (Recommended - 3 steps)

```bash
git clone <repo-url>
cd neighbourhood-watch
docker compose up --build

# Done! 🎉
# Frontend: http://localhost:8080
# API: http://localhost:8000/api/
# Postgres: localhost:5432 (user: nhwz, pass: nhwz)
```

### Option 2: Local Development (10 steps)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --settings=config.settings.local
python manage.py runserver --settings=config.settings.local

# In another terminal, Frontend
cd frontend
npm install
npm run dev

# Done! Open http://localhost:5173
```

---

## Test Account Credentials

After starting the services, use these test accounts:

### Resident Account
- Email: `resident@example.com`
- Password: `testpass123`

### Coordinator Account  
- Email: `coordinator@example.com`
- Password: `testpass123`

### Admin Account
- Email: `admin@example.com`
- Password: `testpass123`

**To create test accounts:**

```bash
# Enter Django shell
docker exec -it nhwz-api-1 python manage.py shell

# Then in the shell:
from apps.accounts.models import User, Role

role = Role.objects.get(code='resident')
User.objects.create_user(
    email='newuser@example.com',
    password='testpass123',
    full_name='New User',
    phone_number='+263771234567',
    national_id='12345678A',
    role=role
)
```

---

## Common Tasks

### View API Documentation

```bash
curl http://localhost:8000/api/
curl http://localhost:8000/api/schema/
```

### Check Database Status

```bash
docker exec nhwz-postgres-1 pg_isready -U nhwz
```

### View Logs

```bash
# API logs
docker compose logs -f api

# Database logs
docker compose logs -f postgres

# All services
docker compose logs -f
```

### Reset Everything

```bash
docker compose down -v
docker compose up --build
```

### Access Database Directly

```bash
docker exec -it nhwz-postgres-1 psql -U nhwz -d nhwz

# Sample queries:
SELECT * FROM accounts_user;
SELECT * FROM incidents_incident;
```

### Run Tests

```bash
docker exec nhwz-api-1 python manage.py test apps --settings=config.settings.test
```

---

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000
kill -9 <PID>

# Or use different port
python manage.py runserver 8001 --settings=config.settings.local
```

### Database Connection Failed

```bash
# Check postgres is running
docker compose logs postgres

# Recreate postgres
docker compose down postgres
docker compose up postgres

# Run migrations again
docker exec nhwz-api-1 python manage.py migrate --settings=config.settings.production
```

### Frontend Not Connecting to API

```bash
# Check API is running
curl http://localhost:8000/api/health/

# Update VITE_API_BASE_URL in .env
export VITE_API_BASE_URL=http://localhost:8000

# Restart frontend
npm run dev
```

### Docker Compose Issues

```bash
# Verify Docker is running
docker ps

# Check Docker daemon logs (macOS)
log stream --predicate 'process == "Docker"'

# Rebuild everything
docker compose down -v
docker system prune -a
docker compose up --build
```

---

## What's Next?

- ✅ Backend running: http://localhost:8000
- ✅ Frontend running: http://localhost:5173 or http://localhost:8080
- 📖 Read [API Documentation](README.md#api-documentation)
- 🧪 Run tests: `docker exec nhwz-api-1 python manage.py test apps --settings=config.settings.test`
- 🚀 Deploy to production: See [Deployment Guide](README.md#deployment-guide)
- 📚 Learn more: Check `docs/` folder

---

## Need Help?

- 📧 Email: support@example.com
- 💬 Slack: #neighbourhood-watch
- 🐛 Issues: GitHub issues
- 📖 Docs: https://docs.example.com

Happy coding! 🚀
