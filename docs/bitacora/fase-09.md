# Bitácora · Fase 9 — Despliegue

- **Rama:** `fase/09-despliegue` · **Fecha:** 2026-11-13 · **Estado:** ✅ en revisión

## Qué
Blueprint de Render, job de despliegue en CI condicionado a que todo pase, carga de demo en un
paso, respaldo y restauración probados, y verificación de extremo a extremo.

## Cómo / por qué
- `autoDeploy: false` y despliegue por *deploy hook* desde CI: nada llega a producción sin pasar
  lint, tests, SAST, pip-audit, Trivy y `check --deploy`.
- Base de datos y Valkey sin acceso público (`ipAllowList: []`); secretos fuera del repositorio.
- `backup.py` usa `PGPASSWORD` en el entorno (nunca en la línea de comandos) y valida la cadena de
  auditoría tras restaurar.

## Evidencias
- Respaldo real de la BD de desarrollo: 495 KB, 83 tablas con datos (`verificar`).
- `scripts/e2e.py`: **7 pasos, 0 errores** (inicio → búsqueda → ficha → carrito de invitado →
  login con fusión del carrito → checkout con recogida → pasarela de pruebas → pago aprobado →
  pedido → factura PDF). [Capturas](../capturas/fase-09/).
- Durante el e2e, el checkout rechazó correctamente un producto sin unidades en la tienda de
  recogida (el carrito del cliente demo tenía una Switch 2 agotada en esa sede).

## Pendientes
El despliegue real en Render requiere la cuenta del proyecto y las llaves del sandbox de Wompi.
