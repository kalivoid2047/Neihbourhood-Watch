# Procfile — used by Heroku, Render, Railway, and Foreman.
#
# The 'web' process uses daphne (ASGI) so WebSocket connections work
# alongside regular HTTP.  If you only need HTTP, replace with:
#   web: cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4
#
# $PORT is injected by the PaaS; fall back to 8000 for local foreman use.

web:    cd backend && daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application
worker: cd backend && celery -A config.celery worker --loglevel=info --concurrency=4
beat:   cd backend && celery -A config.celery beat   --loglevel=info
