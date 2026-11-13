"""Gunicorn configuration (production image). Values overridable by environment."""

import os

# The container listens on all interfaces; the platform's proxy fronts it.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# Access logs are off by default: request paths may carry one-time tokens
# (e.g. password-reset keys). Application logs are JSON with masking (A09).
accesslog = os.environ.get("GUNICORN_ACCESS_LOG") or None
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")

# Request-size hardening.
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
