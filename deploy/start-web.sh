#!/bin/sh
# Render web start: build the BI lake on this disk if missing, then serve.
set -eu
python manage.py ensure_lake
exec gunicorn config.wsgi:application --config gunicorn.conf.py
