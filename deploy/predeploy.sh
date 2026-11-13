#!/bin/sh
# Render pre-deploy: migrations, roles and demo data (idempotent).
set -eu
python manage.py migrate --noinput
python manage.py bootstrap_demo --sin-bi
