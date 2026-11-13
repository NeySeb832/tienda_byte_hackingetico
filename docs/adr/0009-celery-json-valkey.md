# ADR-0009: Celery con serializador JSON sobre Valkey/Redis

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
Hay trabajo en segundo plano: correos, expiración de reservas, el pipeline de analítica y las alertas.
Render ofrece un *Key Value* gestionado, compatible con Redis y basado en Valkey 8. OWASP A08 prohíbe
deserializar datos no confiables con `pickle`.

## Decisión
- Celery 5 con `task_serializer`, `result_serializer` y `accept_content` limitados a `json`, además de
  `acks_late`, `prefetch_multiplier=1` y límites de tiempo por tarea.
- Celery Beat con `django-celery-beat`: el calendario vive en la BD y se administra desde el panel.
- **Valkey 8** en local (Docker) y en producción: usa el protocolo de Redis y es la misma tecnología de
  Render Key Value.
- Si el plan de Render no admite un worker, se usa un modo alterno con `CELERY_TASK_ALWAYS_EAGER` y los
  cron jobs de la plataforma. Se documenta en la Fase 9.

## Consecuencias
- Las tareas solo reciben tipos JSON (IDs y strings), nunca objetos de modelo.
- Hay paridad entre desarrollo y producción.

## Alternativas consideradas
- **RQ o Dramatiq**: son más simples, pero no tienen un programador de tareas tan integrado con Django.
- **pickle**: se descarta por el riesgo de ejecución remota de código.
