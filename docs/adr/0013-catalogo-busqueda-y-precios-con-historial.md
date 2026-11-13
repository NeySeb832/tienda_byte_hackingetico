# ADR-0013: Búsqueda en PostgreSQL y precios con historial inmutable

- **Estado:** Aceptada
- **Fecha:** 2026-11-13

## Contexto
El catálogo necesita búsqueda que tolere tildes, errores de tipeo y la forma en que habla el
cliente ("play 5"), filtros con conteos y precios por variante. Además, la Ley 1480 de 2011 y las
instrucciones de la SIC prohíben anunciar un "precio anterior" que no se cobró de verdad.

## Decisión
1. **Búsqueda sin servicios externos:** texto completo de PostgreSQL (`SearchVector` con
   configuración `spanish`, nombre con peso A) sobre un `search_text` normalizado sin tildes,
   combinado con similitud de trigramas (`pg_trgm`, umbral 0,55) y coincidencia por subcadena.
   El índice lo reconstruye `catalog.services.refresh_search_index`. Los sinónimos viven en
   `Platform.aliases` y `Product.search_keywords`.
2. **Motor de precios con dos modos:** precio fijo por variante, o precio base más modificadores
   por valor de opción. Todo cambio pasa por `pricing.services` y queda en `PriceHistory`, que
   es *append-only* en el ORM y con un trigger en la BD. Los cambios programados los aplica una
   tarea de Celery Beat cada 5 minutos con `SELECT … FOR UPDATE SKIP LOCKED`.
3. **Precio anterior honesto:** solo se muestra tachado tras una bajada real en los últimos
   30 días, y el valor de referencia es el **más bajo** cobrado en los 30 días previos a esa bajada
   (criterio equivalente a la directiva Omnibus de la UE).

## Consecuencias
- Sin Elasticsearch ni Meilisearch: un servicio menos que desplegar y asegurar. El volumen del
  catálogo (cientos o pocos miles de productos) está muy por debajo del límite de PostgreSQL.
- El historial de precios no se puede reescribir ni borrar; una variante con historial se
  desactiva, no se elimina (FK `PROTECT`).
- Hay que reconstruir el índice de búsqueda al cambiar nombres, plataformas o variantes (los
  servicios ya lo hacen).
- El umbral de trigramas es un compromiso: con 0,45 "timon" coincidía con "limón".

## Alternativas consideradas
- **Meilisearch/Elasticsearch:** mejor relevancia, pero otro servicio con su superficie de ataque.
- **`icontains` sin índice:** lento y sin tolerancia a errores.
- **Guardar "precio antes" a mano en el producto:** permite inventar descuentos; descartado.
