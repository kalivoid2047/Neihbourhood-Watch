# Contributing to Neighbourhood Watch Zimbabwe

We're excited to have you contribute! This document will guide you through the process.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Security](#security)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- Be respectful and professional
- Welcome diverse perspectives
- Focus on constructive criticism
- Report harassment to support@example.com

## Getting Started

### 1. Fork & Clone

```bash
# Fork on GitHub, then:
git clone https://github.com/your-username/neighbourhood-watch.git
cd neighbourhood-watch
git remote add upstream https://github.com/2047-tech/neighbourhood-watch.git
```

### 2. Create Feature Branch

```bash
git checkout -b feature/my-feature
# or for bug fixes
git checkout -b fix/bug-description
```

### 3. Set Up Development Environment

```bash
# Using Docker (recommended)
docker compose up --build

# Or locally
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

## Development Workflow

### Backend Changes

1. **Add Model Changes**:
   ```bash
   cd backend
   python manage.py makemigrations --settings=config.settings.local
   python manage.py migrate --settings=config.settings.local
   ```

2. **Add Tests**:
   ```bash
   # Create test file in apps/*/tests/
   # Run tests
   python manage.py test apps --settings=config.settings.test
   ```

3. **Check Code Quality**:
   ```bash
   # Install dev tools
   pip install black flake8 isort
   
   # Format code
   black .
   isort .
   
   # Check style
   flake8 .
   ```

### Frontend Changes

1. **Start Dev Server**:
   ```bash
   cd frontend
   npm run dev
   ```

2. **Create Component**:
   ```bash
   # Create file in src/components/ or src/pages/
   # Import Tailwind components from src/components/ui.jsx
   # Test in browser at http://localhost:5173
   ```

3. **Build & Test**:
   ```bash
   npm run build
   npm run preview
   ```

## Coding Standards

### Python (Backend)

**Style Guide**: PEP 8 with Black formatter

```python
# ✅ Good
def create_incident(user: User, title: str, category: str) -> Incident:
    """Create a new incident and audit log."""
    incident = Incident.objects.create(
        reporter=user,
        title=title,
        category=category,
    )
    create_audit_log(action="incident_created", actor=user, entity=incident)
    return incident

# ❌ Bad
def createIncident(u,t,c):
    i=Incident.objects.create(reporter=u,title=t,category=c)
    return i
```

**Naming Conventions**:
- Variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_private_method`

**Imports**:
```python
# Standard library
import os
from datetime import datetime

# Third-party
from django.db import models
from rest_framework import serializers

# Local
from .models import Incident
from apps.audit.services import create_audit_log
```

**Comments & Docstrings**:
```python
def verify_incident(incident: Incident, user: User) -> None:
    """
    Verify an incident and record the verification.
    
    Args:
        incident: The incident to verify
        user: The user verifying (coordinator/admin)
    
    Raises:
        PermissionError: If user cannot verify incidents
    """
    if not can_verify(user):
        raise PermissionError()
    
    incident.verified_by = user
    incident.save()
```

### JavaScript (Frontend)

**Style Guide**: ESLint with React conventions

```javascript
// ✅ Good
export default function IncidentCard({ incident, onVerify }) {
  const handleVerify = async () => {
    try {
      await verifyIncident(incident.id);
      onVerify();
    } catch (error) {
      console.error('Verification failed:', error);
    }
  };

  return (
    <Card>
      <h3>{incident.title}</h3>
      <Button onClick={handleVerify}>Verify</Button>
    </Card>
  );
}

// ❌ Bad
function IncidentCard(props) {
  return <div><h3>{props.incident.title}</h3></div>;
}
```

**Naming Conventions**:
- Variables: `camelCase`
- Components: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Event handlers: `handleEventName`

**Component Structure**:
```javascript
import { useState } from 'react';
import { Button, Card } from '@/components/ui';
import { verifyIncident } from '@/api';

export default function IncidentCard({ incident }) {
  // State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Event handlers
  const handleVerify = async () => {
    setLoading(true);
    try {
      await verifyIncident(incident.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Render
  return (
    <Card>
      <h3>{incident.title}</h3>
      <Button onClick={handleVerify} disabled={loading}>
        Verify
      </Button>
      {error && <p className="text-danger-600">{error}</p>}
    </Card>
  );
}
```

## Testing

### Backend Tests

```bash
# Run all tests
python manage.py test apps --settings=config.settings.test

# Run specific app
python manage.py test apps.incidents --settings=config.settings.test

# Run specific test class
python manage.py test apps.incidents.tests.test_phase3_incidents_api --settings=config.settings.test

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test apps --settings=config.settings.test
coverage report
coverage html  # Open htmlcov/index.html
```

**Writing Tests**:
```python
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User, Role

class IncidentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role = Role.objects.create(code='resident', name='Resident')
        self.user = User.objects.create_user(
            email='test@example.com',
            password='test123',
            full_name='Test User',
            phone_number='+263771234567',
            national_id='12345678A',
            role=self.role
        )
    
    def test_resident_can_create_incident(self):
        """Test that residents can create incidents."""
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/incidents/', {
            'title': 'Test Incident',
            'description': 'Test',
            'category': 'theft',
            'latitude': '17.8252',
            'longitude': '31.0335',
            'occurred_at': '2024-01-15T10:00:00Z',
        })
        self.assertEqual(response.status_code, 201)
```

### Frontend Tests (Future)

```bash
# Run tests
npm test

# Watch mode
npm test -- --watch

# Coverage
npm test -- --coverage
```

## Submitting Changes

### 1. Commit Your Changes

```bash
git add .
git commit -m "feat: add incident verification workflow"

# Run tests before committing
python manage.py test apps --settings=config.settings.test
```

### 2. Push to Your Fork

```bash
git push origin feature/my-feature
```

### 3. Create Pull Request

- Push to GitHub
- Click "New Pull Request"
- Select base: `main`, compare: `feature/my-feature`
- Fill out PR template:
  ```markdown
  ## Description
  Brief description of changes
  
  ## Type of Change
  - [ ] Bug fix
  - [ ] New feature
  - [ ] Documentation update
  - [ ] Performance improvement
  
  ## How Has This Been Tested?
  Describe your test plan
  
  ## Checklist
  - [ ] Tests pass
  - [ ] Documentation updated
  - [ ] No new warnings
  - [ ] Code follows style guidelines
  ```

### 4. Code Review

- Address feedback from reviewers
- Update code as needed
- Re-run tests
- Approve when ready

### 5. Merge

Maintainers will merge to `main` branch.

## Commit Message Guidelines

Follow the Conventional Commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Test additions/changes
- `chore`: Build, dependencies, etc.

**Examples**:
```
feat(incidents): add incident verification workflow
fix(auth): handle expired token refresh correctly
docs: add API documentation
test(incidents): add tests for status transitions
chore: update dependencies
```

## Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

1. Email: security@example.com
2. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if applicable)

3. Allow 48 hours for response

### Security Best Practices

When contributing:

- ✅ Use parameterized queries (Django ORM handles this)
- ✅ Validate all user inputs
- ✅ Escape output in templates
- ✅ Use HTTPS in production
- ✅ Don't commit secrets or tokens
- ✅ Use environment variables for configuration

---

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [React Documentation](https://react.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [PEP 8 Style Guide](https://pep8.org/)
- [Google's Python Style Guide](https://google.github.io/styleguide/pyguide.html)

## Questions?

- 📧 support@example.com
- 💬 GitHub Discussions
- 🐛 GitHub Issues

Thank you for contributing! 🙏
