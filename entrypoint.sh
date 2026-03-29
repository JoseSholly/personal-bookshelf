#!/bin/sh
set -e

echo "Running migrations and collecting static..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# # Run seed only once (or make seed_books idempotent)
# if [ ! -f /app/.books_seeded ]; then
#     echo "Seeding books (first run only)..."
#     python manage.py seed_books
#     touch /app/.books_seeded
# fi

echo "Starting Gunicorn..."
exec gunicorn bookshelf.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 10 --timeout 300