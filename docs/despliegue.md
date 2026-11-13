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
1. En Render: **New → Blueprint** sobre el repositorio (rama `main`) y **Deploy Blueprint**.
   No hay que escribir secretos: Render genera `DJANGO_SECRET_KEY`, `BYTE_BLIND_INDEX_KEY`,
   `BYTE_FIELD_ENCRYPTION_KEYS` (se deriva una clave Fernet) y `BYTE_DEMO_PASSWORD`. El dominio
   (`RENDER_EXTERNAL_HOSTNAME`) alimenta `ALLOWED_HOSTS`, CSRF y `BYTE_SITE_URL`.
2. El *pre-deploy* (`deploy/predeploy.sh`) migra y carga la demo (idempotente); el arranque web
   (`deploy/start-web.sh`) construye el data lake si falta y lanza gunicorn. Render ejecuta los
   comandos **sin shell ni comillas**: por eso van en scripts.
3. Arranca con el **simulador de pagos** y los correos al log. Para el sandbox real, cargar en
   *Environment* de `byte-web`, `byte-worker` y `byte-beat`:
   - `BYTE_PAYMENT_GATEWAY=wompi`, `WOMPI_PUBLIC_KEY`, `WOMPI_INTEGRITY_SECRET`, `WOMPI_EVENTS_SECRET`;
   - `TURNSTILE_SITE_KEY` y `TURNSTILE_SECRET_KEY`;
   - `DJANGO_EMAIL_BACKEND=anymail.backends.brevo.EmailBackend` y `DJANGO_ANYMAIL`;
   - `DJANGO_ADMIN_URL` (ruta aleatoria; sin ella el admin de Django no se publica) y `SENTRY_DSN`.
4. En Wompi (sandbox) registrar la URL de eventos: `https://<dominio>/pagos/webhook/`.
5. En GitHub: secreto `RENDER_DEPLOY_HOOK_URL` y variable `BYTE_PUBLIC_URL` en el entorno
   `production`. Desde ahí, cada push a `main` despliega **solo si** lint, tests, seguridad e
   imagen pasan (job `deploy`), y luego espera `/healthz`.

**Instancia actual:** https://byte-web-v9h4.onrender.com (la contraseña demo está en
*Environment* de `byte-web`, variable `BYTE_DEMO_PASSWORD`).

## Verificación
- `/healthz` responde `{"status": "ok"}` (BD y caché).
- `python manage.py check --deploy` sin advertencias (`byte.W004` avisa si se usa el simulador).
- `uv run python scripts/e2e.py --base-url https://<dominio>`: compra completa con el cliente demo.

## Respaldos
- Render hace respaldos diarios de PostgreSQL (según el plan).
- Respaldo manual: `uv run python scripts/backup.py respaldar` (formato *custom*, `backups/`).
  `verificar` lista su contenido y `restaurar` pide confirmación escrita y luego ejecuta
  `verify_audit_chain`.
