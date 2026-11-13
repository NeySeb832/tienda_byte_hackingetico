# Bitácora · Fase 3 — Catálogo y precios

- **Rama:** `fase/03-catalogo`
- **Fecha:** 2026-11-13
- **Estado:** ✅ en revisión

## 1. Qué se hizo

- Modelo de catálogo: marcas, plataformas, categorías en árbol, géneros, atributos, opciones,
  variantes (SKU) y ficha de videojuego.
- Motor de precios con dos modos (precio fijo o base + modificadores), historial inmutable,
  cambios programados aplicados por Celery Beat y "precio anterior" honesto.
- Inventario por sede (`StockItem`) y disponibilidad por tienda en la ficha.
- Búsqueda tolerante a tildes y errores, autocompletado, filtros con conteos, orden y paginación.
- Ficha con configurador HTMX, gráfica de precio, comparador de hasta 4 productos y "vistos
  recientemente".
- `seed_demo` con 66 productos y 138 variantes de la lista maestra y 6 sedes.
- El inicio ahora lee categorías y destacados de la base de datos.

## 2. Cómo se hizo

- **Capas:** `catalog/services.py` crea variantes y valida combinaciones; `pricing/services.py`
  es el único lugar que cambia `ProductVariant.price`; los selectors arman listados, facetas y el
  configurador con `Subquery`/`Exists` (sin duplicar filas) y `prefetch_related`.
- **Búsqueda:** `search_text` normalizado (minúsculas, sin tildes) con índice GIN de trigramas, y
  `search_vector` (español, nombre con peso A) con índice GIN. Una consulta coincide por texto
  completo, por subcadena o por similitud de palabra ≥ 0,55.
- **Configurador:** cada opción enlaza al SKU que resulta de cambiar ese valor. Si la
  combinación no existe, el valor se deshabilita, excepto en la primera opción, que salta a la
  variante más parecida para que todas sean alcanzables. Funciona como enlace normal sin
  JavaScript y con HTMX reemplaza solo `#configurador` y actualiza la URL (`?sku=`).
- **Filtros:** formulario "tolerante": los valores que no están en la lista blanca (marca,
  orden, precio mal formado) se descartan en vez de romper la página.
- **Historial de precios:** `AppendOnlyQuerySet` + `save()`/`delete()` que lo impiden, y trigger
  `pricing_pricehistory_append_only` que solo deja poner `changed_by = NULL` (borrado de usuario).
- **Fotos:** 26 nuevas desde Wikimedia Commons con licencia libre, fijadas por SHA-256.

### Problemas encontrados y cómo se resolvieron

| Problema | Solución |
|----------|----------|
| Wikimedia respondió 429 al bajar originales | Miniaturas de 1280 px, `Retry-After` y caché local verificada por SHA-256 |
| El recorte de fondo blanco borraba consolas blancas (PS5 Slim, Dreamcast, Wii, DualSense) | Se revisó una hoja de contacto y esas fotos conservan su fondo |
| Con umbral de trigramas 0,45, "timon" encontraba "verde limón" | Umbral 0,55 (sigue encontrando "plaistation") |
| Los tests de inicio y cabeceras tocaban la BD sin permiso | Ahora el inicio lee la BD: se marcaron con `django_db` |
| `Attribute.__str__` devolvía un texto *lazy* y fallaba al formatear | `str(self.name)` |
| La portada genérica fallaba en productos sin marca | La etiqueta se calcula en el selector |
| El navegador del panel mostraba CSS en caché | Recarga forzada; el CSS servido era el correcto |

## 3. Por qué

- **PostgreSQL y no un motor de búsqueda externo:** un servicio menos que desplegar y asegurar, y
  el volumen del catálogo está muy por debajo de su límite (ADR-0013).
- **Historial inmutable y precio anterior calculado:** la Ley 1480 prohíbe anunciar descuentos
  sobre precios que no se cobraron. Como el precio de referencia se calcula del historial y el
  historial no se puede editar, no hay forma de "inflar" el antes.
- **Sesión con `public_id`:** el comparador y los vistos no guardan PK ni datos personales, y los
  valores alterados en la sesión se ignoran.
- **Datos demo honestos:** se excluyen consolas programadas, copias, emuladores y chips (software
  sin licencia). Los juegos llevan precio de referencia porque ninguna lista los trae; no se
  inventaron descuentos.

## 4. Evidencias

El resumen está en [`00-resumen.svg`](../capturas/fase-03/00-resumen.svg).

| # | Verificación | Resultado |
|---|--------------|-----------|
| 01 | Tests (pytest) contra PostgreSQL 17 | ✅ **530 pasan** (antes 448), cobertura **94,6 %** |
| — | Cobertura de `services.py`/`selectors.py` de catálogo, precios e inventario | ✅ 95–100 % |
| 02–04 | ruff · black · mypy | ✅ (black falló en la primera corrida por `scripts/capturas.py` sin formatear; se formateó y se repitió) |
| 05 | bandit (severidad media o alta) | ✅ 0 hallazgos |
| 06 | pip-audit | ✅ sin vulnerabilidades conocidas (esta fase no agregó dependencias) |
| 07 | `check --deploy` | ✅ |
| 08 | Cabeceras de seguridad | ✅ |
| 09 | Integridad de las librerías JS y Tailwind | ✅ |
| 10 | semgrep `p/django` + `p/python` | ✅ **0 hallazgos** en 152 reglas y 324 archivos |
| 11 | Trivy sobre `byte:local` | ✅ 0 HIGH/CRITICAL corregibles (imagen construida en la Fase 2: esta fase no cambió dependencias ni el Dockerfile) |
| 12 | Matriz de permisos | ✅ al día |
| 13 | Cadena de auditoría (BD de desarrollo, con los eventos de `seed_demo`) | ✅ íntegra |

`scripts/evidencia.py` ahora arma el resumen con el último resultado guardado de cada chequeo,
así repetir uno con `--solo` no borra los demás del resumen.

Tests nuevos de esta fase: servicios del catálogo (combinaciones, modos de precio, índice,
listas de sesión), selectors (búsqueda tolerante, filtros, facetas, orden en lista blanca,
configurador, comparador), motor de precios (manual, recálculo, programados, tarea de Beat,
historial inmutable en ORM y BD), precio anterior honesto, inventario (constraints, reservas) y
`seed_demo` (idempotencia y exclusión de software sin licencia).

Seguridad (`tests/security/test_catalog_security.py`): XSS en búsqueda y sugerencias, comparador
solo por POST con CSRF, sin redirección abierta en `next`, límite de tasa del autocompletado y
ninguna PK interna en las páginas.

### Pantallas (Playwright, BD con `seed_demo`)

Consola del navegador: **0 mensajes y 0 violaciones de CSP**
([`consola-navegador.txt`](../capturas/fase-03/consola-navegador.txt)).

| Pantalla | Captura |
|----------|---------|
| Inicio con categorías y destacados desde la BD | [oscuro](../capturas/fase-03/inicio-escritorio-oscuro.jpg) · [móvil](../capturas/fase-03/inicio-movil-claro.jpg) |
| Catálogo con filtros y conteos | [claro](../capturas/fase-03/catalogo-escritorio-claro.jpg) · [móvil](../capturas/fase-03/catalogo-movil-oscuro.jpg) |
| Categoría PlayStation | [captura](../capturas/fase-03/categoria-playstation-escritorio-oscuro.jpg) |
| Búsqueda con error de tipeo ("plaistation") | [captura](../capturas/fase-03/busqueda-con-error-de-tipeo-escritorio-oscuro.jpg) |
| Filtros: Nintendo usados, menor precio | [captura](../capturas/fase-03/filtros-nintendo-usados-escritorio-oscuro.jpg) |
| Ficha PS5 Slim con configurador | [oscuro](../capturas/fase-03/ficha-ps5-slim-escritorio-oscuro.jpg) · [móvil](../capturas/fase-03/ficha-ps5-slim-movil-claro.jpg) |
| Variante agotada (30.º aniversario) | [captura](../capturas/fase-03/ficha-variante-agotada-escritorio-oscuro.jpg) |
| Precio por modificadores (Series S 1 TB) | [captura](../capturas/fase-03/ficha-precio-por-modificadores-escritorio-oscuro.jpg) |
| Ficha de videojuego (ESRB, PEGI) | [captura](../capturas/fase-03/ficha-juego-escritorio-oscuro.jpg) |
| Producto sin foto (portada genérica) | [captura](../capturas/fase-03/ficha-sin-foto-escritorio-oscuro.jpg) |
| Comparador | [oscuro](../capturas/fase-03/comparador-escritorio-oscuro.jpg) · [móvil](../capturas/fase-03/comparador-movil-claro.jpg) |

## 5. Pendientes y riesgos

- El botón "Agregar al carrito" se conecta en la Fase 4 (carrito y checkout).
- La gestión de catálogo, precios y stock desde el panel propio (con kardex y traslados entre
  sedes) llega en la Fase 5; mientras tanto se usa el admin del superadmin.
- 32 de los 66 productos no tienen foto con licencia libre verificable y usan la portada genérica
  (entre ellos los 12 videojuegos, cuyas carátulas tienen derechos de autor); 3 fotos
  (PS3, PS Vita, 3DS) no se usan porque esos equipos solo figuraban como programados o copias.
- Los precios de los videojuegos son de referencia para la demo.
