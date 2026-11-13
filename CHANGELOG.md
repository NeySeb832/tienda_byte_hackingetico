# Changelog

Todos los cambios relevantes del proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

## [0.1.0] — 2026-11-12 — Fase 1: Fundaciones

### Añadido
- `CLAUDE.md` con las reglas de trabajo, las convenciones, los comandos y el estado de las fases.
- ADR 0001–0011 en `docs/adr/`:
  - 0001: monolito modular.
  - 0002: Django 5.2 LTS + django-csp.
  - 0003: permisos de objeto propios.
  - 0004: dinero e IVA.
  - 0005: dependencias.
  - 0006: frontend sin Node.
  - 0007: pasarela de pagos.
  - 0008: checkout con cuenta.
  - 0009: Celery con JSON.
  - 0010: bitácora.
  - 0011: identificadores públicos.
- Proyecto Django 5.2 LTS con settings por entorno (`base`, `dev`, `test`, `prod`) basados en `django-environ`, Celery y Celery Beat.
- 21 apps con la estructura en capas: `models`, `services`, `selectors`, `forms`, `views`, `permissions` y `tests`.
- Usuario propio `accounts.User`:
  - El email es el login y se guarda en minúsculas, garantizado con `CHECK` en la BD.
  - Tiene `public_id` UUID.
  - Se administra desde un admin adaptado.
- Modelos base `PublicIdModel` y `TimeStampedModel`, y una migración con las extensiones `pg_trgm` y `unaccent`.
- Utilidades de dinero en COP: `to_money` (rechaza `float`), `split_vat`, `round_to_peso`, `format_cop` y el filtro de plantilla `cop`.
- Endpoint `/healthz` que verifica la base de datos y la caché, y responde 200 o 503 sin exponer detalles.
- Layout base con look *gamer*, modo oscuro y claro sin parpadeo, página de inicio, y páginas propias para los errores 400, 403, 403 CSRF, 404 y 500.
- `docker-compose.yml` con web, worker, beat, PostgreSQL 17, Valkey 8 y Tailwind (puertos solo en `127.0.0.1`).
- `Dockerfile` multi-etapa: `deps`, `assets`, `dev` y `runtime`, con usuario no root.
- CI en GitHub Actions: lint y tipos → tests con cobertura → seguridad → imagen con Trivy.
- Dependabot con cooldown y `pre-commit`.
- `scripts/vendor_assets.py`, `scripts/evidencia.py` y `scripts/capturas.py` (bitácora con evidencias).
- `docs/modelo-datos.md` con el diagrama ER por dominio, la máquina de estados del pedido y el modelo estrella.
- Página de inicio de tienda en línea:
  - barra de anuncios y slider accesible (scroll-snap, teclado, pausa según WCAG 2.2.2, respeta "reducir movimiento");
  - beneficios y categorías con imagen;
  - 8 consolas y 4 controles destacados con los precios de la lista maestra;
  - retoma, servicio técnico con tarifas, marcas y un pie de página con medios de pago;
  - buscador también en móvil.
- 14 fotos reales de producto de Wikimedia Commons con licencia libre, procesadas por `scripts/product_images.py` (SHA-256 fijado, fondo removido, WebP sin EXIF, 680 KB en total), y la página `/creditos-imagenes/`.
- Pillow 13 como dependencia (procesamiento de imágenes).

### Cambiado
- La interfaz se presenta como un producto real: se eliminaron el bloque "Estado del proyecto" y todas las referencias a fases o al proyecto académico (indicación del usuario).

### Seguridad
- Cuarentena de 7 días en la resolución de dependencias (`exclude-newer`), lock con hashes e instalación en Docker con `--require-hashes`.
- Imágenes Docker fijadas por digest y GitHub Actions fijadas por SHA, con `permissions: contents: read`.
- htmx 2.0.11 y @alpinejs/csp 3.17.5 se sirven localmente y se verifican contra el `integrity` sha512 de npm. El binario de Tailwind 4.3.5 se verifica contra su `sha256sums.txt`; la descarga automática sin verificar de django-tailwind-cli está deshabilitada.
- CSP estricta con nonce por petición (sin `unsafe-inline` ni `unsafe-eval`) y Alpine en versión CSP.
- Cabeceras de seguridad:
  - `X-Frame-Options: DENY`.
  - `nosniff`.
  - `Referrer-Policy`.
  - COOP y CORP.
  - `Permissions-Policy`.
- En producción: HSTS de 1 año con preload, cookies `Secure` con prefijo `__Host-` y `SECURE_SSL_REDIRECT`.
- Argon2id como primer hasher de contraseñas.
- Celery acepta solo JSON.
- La API deniega por defecto (`IsAuthenticated`) y tiene throttling. El esquema OpenAPI es solo para el personal.
- El admin de Django vive en una ruta oculta configurada por variable de entorno; `/admin/` responde 404. Los checks propios `byte.E001`, `byte.W001` y `byte.W002` detectan rutas inválidas o predecibles.
- ID de correlación por petición (`X-Request-ID`), generado siempre en el servidor.
- Logs JSON con enmascarado de datos sensibles.
- Páginas de error genéricas que no exponen trazas internas.
- Límites de tamaño para las peticiones y los archivos subidos.
- Los access logs de Gunicorn están desactivados por defecto, porque las rutas pueden llevar tokens.
- Las fotos de producto se verifican por SHA-256 contra el manifiesto (no con el SHA-1 que publica Commons, porque no es resistente a colisiones; hallazgo de semgrep corregido) y se rechazan las licencias no libres. Se eliminan los metadatos EXIF.
- El catálogo excluye por política los productos y servicios que implican software sin licencia (consolas "programadas", chips).

### Corregido (validación con Docker)
- `staticfiles/` era ilegible para el usuario de la app en la imagen: los permisos estrictos de los archivos subidos (`0o640`) se aplicaban también a `collectstatic`. Ahora los estáticos usan 644/755 (test de regresión).
- La imagen de producción incluía las herramientas de seguridad (semgrep, bandit, pip-audit): `requirements/prod.txt` se exporta con `--no-default-groups`. La imagen bajó de 978 MB a 472 MB.
- El worker de Celery no registraba la ejecución de tareas: receptor `setup_logging` que aplica el `LOGGING` de Django (JSON enmascarado).
- `scripts/evidencia.py` en consolas Windows (UTF-8). Nueva verificación con Trivy fijado por digest.

### Seguridad (validación con Docker)
- Semgrep: las fotos se verifican con SHA-256 en vez de SHA-1. Resultado: 0 hallazgos.
- Trivy: se aplican los parches de seguridad de Debian en la imagen base (zlib CVE-2026-76844 y CVE-2026-85091). Resultado: 0 vulnerabilidades HIGH/CRITICAL corregibles.
- bandit B310 mitigado: las descargas aceptan solo `https://` y la llamada está aislada en `_open_https()`.

### Notas
- Las dependencias se agregan en la fase que las usa. En esta fase solo entraron las de la base del proyecto.
- Versiones verificadas el 12-nov-2026; el detalle está en el ADR-0005.
