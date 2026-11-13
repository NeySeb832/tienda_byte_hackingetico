# Despliegue en Render

## Arquitectura
`render.yaml` (Blueprint) crea:

| Servicio | Tipo | Comando |
|----------|------|---------|
| `byte-web` | Web (Docker, etapa `runtime`) | gunicorn; `preDeployCommand`: `migrate` + `setup_roles`; disco `/var/data` para el data lake |
| `byte-worker` | Worker | `celery worker` |
| `byte-beat` | Worker | `celery beat` con `DatabaseScheduler` |
| `byte-db` | PostgreSQL 17 | solo red privada |
| `byte-valkey` | Key Value (Valkey) | `noeviction` para no perder tareas |

## Pasos
1. En Render: **New → Blueprint** sobre el repositorio (rama `main`).
2. Completar las variables marcadas `sync: false`:
   - `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` (dominio de Render);
   - `DJANGO_ADMIN_URL` (ruta aleatoria);
   - `BYTE_FIELD_ENCRYPTION_KEYS`:
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`;
   - `BYTE_SITE_URL`;
   - llaves del **sandbox** de Wompi y de Turnstile;
   - `DJANGO_ANYMAIL` (`{"BREVO_API_KEY": "..."}`);
   - `BYTE_DEMO_PASSWORD`;
   - `SENTRY_DSN` (opcional).
   `DJANGO_SECRET_KEY` y `BYTE_BLIND_INDEX_KEY` las genera Render.
3. En Wompi (sandbox) registrar la URL de eventos: `https://<dominio>/pagos/webhook/`.
4. Cargar la demo desde el *shell* de `byte-web`: `python manage.py bootstrap_demo`.
5. En GitHub: secreto `RENDER_DEPLOY_HOOK_URL` y variable `BYTE_PUBLIC_URL` en el entorno
   `production`. Desde ahí, cada push a `main` despliega **solo si** lint, tests, seguridad e
   imagen pasan (job `deploy`), y luego espera `/healthz`.

## Verificación
- `/healthz` responde `{"status": "ok"}` (BD y caché).
- `python manage.py check --deploy` sin advertencias (`byte.W004` avisa si se usa el simulador).
- `uv run python scripts/e2e.py --base-url https://<dominio>`: compra completa con el cliente demo.

## Respaldos
- Render hace respaldos diarios de PostgreSQL (según el plan).
- Respaldo manual: `uv run python scripts/backup.py respaldar` (formato *custom*, `backups/`).
  `verificar` lista su contenido y `restaurar` pide confirmación escrita y luego ejecuta
  `verify_audit_chain`.
