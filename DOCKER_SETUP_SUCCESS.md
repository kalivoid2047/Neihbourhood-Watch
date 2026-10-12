# ✅ Docker Setup Complete!

Your **Neighbourhood Watch Zimbabwe** application is now running! Here's what's active:

## 🟢 All Services Running

| Service | Status | URL | Credentials |
| --- | --- | --- | --- |
| **API** | ✅ Running | http://localhost:8000 | - |
| **Frontend** | ✅ Running | http://localhost:8080 | - |
| **Database** | ✅ Running | localhost:5432 | user: `nhwz`, pass: `nhwz` |
| **Redis** | ✅ Running | localhost:6379 | - |
| **MinIO** | ✅ Running | http://localhost:9001 | user: `nhwz`, pass: `nhwz-secret` |
| **Nginx** (Reverse Proxy) | ✅ Running | http://localhost:8080 | - |

## 🎯 Quick Access

### Frontend Application
👉 **http://localhost:8080**

The modern React UI with Tailwind CSS is served through Nginx.

### API Endpoints
👉 **http://localhost:8000/api/**

### Health Check
```bash
curl http://localhost:8000/api/health/
# Response: {"status":"ok","service":"nhwz-api","database":"ok","debug":true}
```

### API Documentation
👉 **http://localhost:8000/api/schema/**

View the OpenAPI schema for all endpoints.

## 👤 Test Accounts

Use these credentials to test the application:

### Test User
- **Email**: `resident@example.com`
- **Password**: `testpass123`
- **Role**: Resident

### Test Coordinator
- **Email**: `coordinator@example.com`
- **Password**: `testpass123`
- **Role**: Coordinator

### Create Additional Test Accounts

```bash
# Access Django shell
docker exec -it neihbourhoodwatch-api-1 python manage.py shell

# Then in the shell:
from apps.accounts.models import User, Role

# Create a new resident
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

## 📊 Database Access

### Connect to PostgreSQL
```bash
docker exec -it neihbourhoodwatch-postgres-1 psql -U nhwz -d nhwz
```

### Useful SQL Queries
```sql
-- List all users
SELECT id, email, full_name, role_id FROM accounts_user;

-- List all incidents
SELECT id, title, status, created_at FROM incidents_incident;

-- List pending verification requests
SELECT id, status, created_at FROM accounts_verification_request WHERE status = 'pending';

-- Check user count by role
SELECT r.name, COUNT(u.id) as count FROM accounts_role r LEFT JOIN accounts_user u ON r.id = u.role_id GROUP BY r.id, r.name;
```

## 🛠️ Common Docker Commands

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f postgres
docker compose logs -f nginx

# Last 100 lines
docker compose logs --tail 100 api
```

### Access Service Shells
```bash
# API container
docker exec -it neihbourhoodwatch-api-1 bash

# Database
docker exec -it neihbourhoodwatch-postgres-1 psql -U nhwz -d nhwz

# Redis
docker exec -it neihbourhoodwatch-redis-1 redis-cli
```

### Run Commands in Container
```bash
# Run Django management commands
docker exec neihbourhoodwatch-api-1 python manage.py migrate --settings=config.settings.production

# Run tests
docker exec neihbourhoodwatch-api-1 python manage.py test apps --settings=config.settings.test

# Create superuser
docker exec -it neihbourhoodwatch-api-1 python manage.py createsuperuser --settings=config.settings.production
```

## ⚠️ Troubleshooting

### API Not Responding
```bash
# Check if container is running
docker ps | grep api

# View API logs
docker compose logs api

# Restart API
docker compose restart api
```

### Database Connection Error
```bash
# Check PostgreSQL is running
docker compose logs postgres

# Check database connectivity
docker exec neihbourhoodwatch-postgres-1 pg_isready -U nhwz
```

### Port Already in Use
If port 8080 is already in use, modify `docker-compose.yml`:
```yaml
ports:
  - "8081:80"  # Changed from 8080:80
```

Then restart:
```bash
docker compose down
docker compose up -d
```

Access at `http://localhost:8081`

### Reset Everything
```bash
# Stop and remove all containers and volumes
docker compose down -v

# Rebuild and start fresh
docker compose up --build
```

## 📱 Testing the Application

### 1. Access Frontend
- Open http://localhost:8080
- You should see the home page with features and CTA buttons

### 2. Register New User
- Click "Register" button
- Fill in form with:
  - Email: `yourtest@example.com`
  - Password: `testpass123`
  - Name: `Test User`
  - Phone: `+263771234567`
  - National ID: `12345678Z`
- Click "Create Account"

### 3. Login
- Navigate to http://localhost:8080
- Click "Login"
- Use credentials from above
- You'll be redirected to dashboard

### 4. Create an Incident (Phase 3)
- After login, navigate to "Incidents"
- Click "New Incident"
- Fill in incident details
- Submit

### 5. Test API Directly
```bash
# Get home page
curl http://localhost:8000/api/

# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "full_name": "Test User",
    "phone_number": "+263771234567",
    "national_id": "12345678A"
  }'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}'

# Get your profile (requires token)
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/api/users/me/
```

## 📚 Next Steps

1. **Read Documentation**
   - Start with README.md for complete guide
   - Check QUICKSTART.md for common tasks

2. **Explore the API**
   - Visit http://localhost:8000/api/ to see available endpoints
   - Try curl commands above

3. **Test the UI**
   - Register a new account
   - Try different user roles
   - Test incident reporting

4. **Run Tests**
   ```bash
   docker exec neihbourhoodwatch-api-1 python manage.py test apps --settings=config.settings.test
   ```

5. **Develop Locally** (instead of Docker)
   - See QUICKSTART.md for local development setup
   - Use local Python and npm

## 🎓 Learn More

- **README.md**: Complete project guide
- **QUICKSTART.md**: 5-minute setup
- **CONTRIBUTING.md**: Developer guide
- **docs/ARCHITECTURE.md**: System design
- **DOCUMENTATION_INDEX.md**: All docs index

## 🚀 Deployment

When ready to deploy to production:
1. Follow README.md Deployment Guide
2. Review .env.example for configuration
3. Set up SSL certificates
4. Configure database backups
5. Set up monitoring

## 💡 Tips

- Logs are viewable with `docker compose logs -f`
- Database is persistent (won't reset on container restart)
- Use `docker compose down -v` to completely reset
- Frontend is served through Nginx for production-like experience
- API is served through Gunicorn for production-like experience

## 📞 Need Help?

- Check troubleshooting section above
- Review QUICK_REFERENCE.md
- See DOCUMENTATION_INDEX.md for all guides
- Report issues on GitHub

---

✅ **Your setup is complete and working!**

Next: Open http://localhost:8080 and start exploring! 🎉
