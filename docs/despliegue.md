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


## Verificación
- `/healthz` responde `{"status": "ok"}` (BD y caché).
- `python manage.py check --deploy` sin advertencias (`byte.W004` avisa si se usa el simulador).
- `uv run python scripts/e2e.py --base-url https://<dominio>`: compra completa con el cliente demo.

## Respaldos
- Render hace respaldos diarios de PostgreSQL (según el plan).
- Respaldo manual: `uv run python scripts/backup.py respaldar` (formato *custom*, `backups/`).
  `verificar` lista su contenido y `restaurar` pide confirmación escrita y luego ejecuta
  `verify_audit_chain`.
