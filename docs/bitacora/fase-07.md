# Bitácora · Fase 7 — Big Data / BI

- **Rama:** `fase/07-bigdata` · **Fecha:** 2026-11-13 · **Estado:** ✅ en revisión

## Qué
`seed_bigdata` (2 años de histórico sintético, ~70 000 líneas), pipeline medallón con DuckDB
(bronce → plata → oro), modelo estrella, segmentación RFM, pronóstico mensual, tablero BI con
ECharts en `/panel/analytics/`, tarea nocturna y job opcional de PySpark.

## Cómo
- Histórico determinista con estacionalidad (diciembre, Black Friday, fines de semana) y
  crecimiento anual; clientes como claves opacas.
- Extracción de PostgreSQL seudonimizada (HMAC del id), escritura atómica por tabla.
- SQL constante sobre vistas registradas con la API de DuckDB (bandit B608 resuelto sin
  silenciarlo).

## Por qué
Ver ADR-0017: cero infraestructura nueva, sin datos personales en el lago y modelos explicables.

## Evidencias
| Verificación | Resultado |
|--------------|-----------|
| Tests (BD recién creada) | ✅ **713 pasan**, cobertura **93 %** |
| ruff · black · mypy · bandit · pip-audit (con DuckDB 2.0.0) · check --deploy · cabeceras · vendor (con ECharts) · matriz · auditoría | ✅ |
| semgrep | ✅ **0 hallazgos** en 152 reglas y 410 archivos |
| Trivy (imagen reconstruida con DuckDB) | ✅ 0 HIGH/CRITICAL corregibles |

Bandit marcó el SQL de DuckDB armado con f-strings (B608); en vez de silenciarlo se reescribió con
la API relacional y SQL constante.

Pantallas: [tablero (analista)](../capturas/fase-07/panel-inteligencia-de-negocio-escritorio-oscuro.jpg) ·
[móvil](../capturas/fase-07/panel-inteligencia-de-negocio-movil-claro.jpg) ·
[403 bodega](../capturas/fase-07/403-bodega-en-bi-escritorio-oscuro.jpg). Consola: 0 violaciones de CSP.

## Pendientes
El job de PySpark no se ejecuta en CI (requiere Java); el pronóstico no modela lanzamientos.
