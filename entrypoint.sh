#!/bin/sh
set -e

echo "Starting entrypoint: running migrations and collecting static files"

# Apply database migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Seed database
python manage.py seed_books

echo "Entrypoint complete — executing command"

# Start WSGI
echo "Starting Gunicorn..."
exec gunicorn bookshelf.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
