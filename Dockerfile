# syntax=docker/dockerfile:1.7
# Byte — multi-stage image. Base image pinned by digest; dependencies installed with
# --require-hashes from requirements/*.txt (exported from uv.lock). See ADR-0005.
ARG PYTHON_IMAGE=python:3.12-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

# ---------------------------------------------------------------------------
# base: common runtime environment
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"
# Debian security patches released after the pinned base image was built
# (e.g. zlib CVE-2026-76844/85091 reported by Trivy). Keeps the image free of
# fixable HIGH/CRITICAL vulnerabilities until the official image is rebuilt.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# ---------------------------------------------------------------------------
# deps: production dependencies (hash-verified, no resolution at build time)
# ---------------------------------------------------------------------------
FROM base AS deps
COPY requirements/prod.txt /tmp/requirements/prod.txt
RUN python -m venv /opt/venv \
 && pip install --require-hashes --no-deps -r /tmp/requirements/prod.txt

# ---------------------------------------------------------------------------
# assets: compile Tailwind with the checksum-verified standalone CLI (no Node)
# ---------------------------------------------------------------------------
FROM base AS assets
COPY scripts/vendor_assets.py scripts/vendor_assets.py
RUN python scripts/vendor_assets.py --only-tailwind
COPY assets/ assets/
COPY templates/ templates/
COPY apps/ apps/
COPY static/js/ static/js/
RUN .bin/tailwindcss -i assets/css/input.css -o static/css/tailwind.css --minify

# ---------------------------------------------------------------------------
# dev: local development image used by docker compose (code is bind-mounted)
# ---------------------------------------------------------------------------
FROM deps AS dev
COPY requirements/dev.txt /tmp/requirements/dev.txt
RUN pip install --require-hashes --no-deps -r /tmp/requirements/dev.txt
COPY --from=assets /app/.bin/tailwindcss /usr/local/bin/tailwindcss
ENV TAILWIND_CLI_PATH=/usr/local/bin/tailwindcss
RUN groupadd --system --gid 10001 byte \
 && useradd --system --uid 10001 --gid byte --home-dir /app --no-create-home --shell /usr/sbin/nologin byte
USER byte
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---------------------------------------------------------------------------
# runtime: production image (non-root, read-only code owned by root)
# ---------------------------------------------------------------------------
FROM base AS runtime
RUN groupadd --system --gid 10001 byte \
 && useradd --system --uid 10001 --gid byte --home-dir /app --no-create-home --shell /usr/sbin/nologin byte
COPY --from=deps /opt/venv /opt/venv
COPY . .
COPY --from=assets /app/static/css/tailwind.css static/css/tailwind.css
# collectstatic only needs syntactically valid settings: the values below are
# build-time placeholders, never used at runtime.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_SECRET_KEY=build-time-placeholder-only-for-collectstatic-not-used-at-runtime \
    DATABASE_URL=postgres://build@localhost:5432/build \
    REDIS_URL=redis://localhost:6379/0 \
    python manage.py collectstatic --noinput
USER byte
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
