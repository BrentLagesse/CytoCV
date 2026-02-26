#!/bin/bash
set -e

echo "${0}: running migrations."
python manage.py makemigrations accounts
python manage.py makemigrations core
python manage.py migrate


echo "${0}: starting gunicorn..."
exec gunicorn cytocv.wsgi:application \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --workers 3
