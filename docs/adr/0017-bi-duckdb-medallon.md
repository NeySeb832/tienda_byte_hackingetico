# ADR-0017: BI con DuckDB sobre Parquet (arquitectura medallón) y PySpark opcional

- **Estado:** Aceptada
- **Fecha:** 2026-11-13

## Contexto
El módulo de Big Data necesita un histórico masivo, un pipeline por capas, un modelo estrella y
tableros, sin sumar infraestructura pesada a un monolito que se despliega en Render.

## Decisión
- **DuckDB 2.0** (embebido, sin servidor) sobre archivos **Parquet** en `BYTE_DATA_LAKE_DIR`:
  bronce (CSV crudos: histórico sintético y extracción seudonimizada de PostgreSQL), plata
  (tipado, deduplicado, validado) y oro (estrella: `fact_sales`, `dim_date`, `dim_product`,
  `dim_store`, `dim_customer`, más `forecast_monthly`).
- **Sin datos personales en el lago:** el cliente es un HMAC (blind index) del id, nunca el correo.
- **SQL constante:** los archivos se adjuntan con la API relacional de DuckDB; ninguna ruta ni
  valor se interpola en el texto SQL.
- **Modelos explicables:** segmentación RFM por quintiles y pronóstico mensual por tendencia
  lineal × índice estacional, con banda de ±1,96 σ.
- **Tableros con ECharts 6.1** servido localmente (integridad sha512) y datos vía `json_script`.
- **PySpark** como camino de escala (`scripts/spark_gold_job.py`), fuera de las dependencias.
- Pipeline nocturno con Celery Beat (3:00 a. m.).

## Consecuencias
- Cero servicios nuevos; el lago es un directorio (en Render, un disco persistente).
- DuckDB procesa ~70 000 líneas en segundos; PySpark solo tiene sentido a otra escala.

## Alternativas consideradas
- **PySpark como motor principal:** exige Java y un clúster; desproporcionado aquí.
- **pandas + scikit-learn:** dependencias más pesadas para modelos que SQL resuelve.
