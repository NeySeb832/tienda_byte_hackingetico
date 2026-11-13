# Changelog

Todos los cambios relevantes del proyecto se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

## [0.3.0] — 2026-11-13 — Fase 3: Catálogo y precios

### Añadido
- **Catálogo** con marcas, plataformas (con sinónimos de búsqueda), categorías en árbol, géneros, atributos configurables y ficha de videojuego (ESRB, PEGI, idiomas, multijugador).
- **Variantes con precio dinámico** en dos modos: precio fijo por variante o precio base más modificadores por opción. Las reglas se validan en `create_variant` (un valor por opción, sin combinaciones repetidas) y en la BD con `CHECK` y `UNIQUE`.
- **Historial de precios** *append-only*: en el ORM y con un trigger de PostgreSQL. Cambios manuales, recálculo por modificadores y **cambios programados** que aplica Celery Beat cada 5 minutos (`SKIP LOCKED`, idempotente). Todo cambio queda en la auditoría.
- **Precio anterior honesto** (Ley 1480): el precio tachado solo aparece tras una bajada real en los últimos 30 días, y es el más bajo cobrado en los 30 días previos. Se muestra también el precio más bajo de los últimos 30 días y una gráfica (sparkline SVG, sin JavaScript) de los últimos 90.
- **Búsqueda** en PostgreSQL: texto completo en español sin tildes y trigramas para tolerar errores ("plaistation", "pokemon", "play 5"). **Autocompletado** con HTMX (límite de 60 por minuto por IP).
- **Listado** con filtros por tipo, marca, plataforma, condición, precio y disponibilidad; conteos por faceta; orden por relevancia, precio, popularidad, recientes y nombre; paginación. Los filtros se actualizan con HTMX y funcionan sin JavaScript.
- **Ficha de producto** con configurador HTMX: opciones agotadas o inexistentes marcadas o deshabilitadas, foto por variante, garantía según la condición, IVA desglosado, disponibilidad por tienda y SKU.
- **Comparador** (hasta 4 productos) y **vistos recientemente**, guardados en la sesión solo con identificadores públicos.
- **Inventario por sede** (`StockItem`) con `select_for_update` y constraints (`quantity ≥ 0`, `0 ≤ reserved ≤ quantity`).
- **`seed_demo`**: 66 productos y 138 variantes de la lista maestra (sin consolas programadas, copias ni chips), 6 sedes y stock determinista. Idempotente.
- El inicio muestra categorías y destacados desde la BD; el menú enlaza a las categorías reales y la búsqueda del encabezado al catálogo.
- 26 fotos nuevas con licencia libre (40 en total); portada genérica para productos sin foto.
- Admin de Django para catálogo, precios (historial de solo lectura) y existencias.
- `scripts/evidencia.py --solo` conserva en el resumen el último resultado de los demás chequeos.
- ADR-0013.

### Corregido
- El recorte del fondo blanco borraba partes de productos blancos (PS5 Slim, Dreamcast, Wii y dos DualSense): esas fotos conservan su fondo.
- La descarga de fotos respeta `Retry-After` de Wikimedia, usa miniaturas de 1280 px y guarda caché verificada por SHA-256.

## [0.2.1] — 2026-11-13 — Correcciones de seguridad de la Fase 2

### Seguridad
- Hallazgos de semgrep de la Fase 2, que el registro anterior omitió por error:
  - El cierre por inactividad del personal armaba la URL de login concatenando `?next=`, lo que permitía inyectar parámetros. Ahora usa `redirect_to_login()`, que codifica el parámetro, y tiene test de regresión.
  - En el validador HIBP, el SHA-1 que exige la API de k-anonimato se marca `usedforsecurity=False`.
  - Resultado: 0 hallazgos en 152 reglas.

## [0.2.0] — 2026-11-12 — Fase 2: Usuarios y seguridad base

### Añadido
- **Autenticación** (django-allauth 65): registro con verificación de correo, login por email, recuperación de contraseña, MFA TOTP con códigos de recuperación, re-autenticación para acciones sensibles y gestión de sesiones activas. Las plantillas usan el estilo de la tienda.
- **Bloqueo progresivo** con django-axes 9 por usuario + IP (5 fallos → 5 min, 10 → 30 min, 20 → 24 h), con página de bloqueo (HTTP 429).
- **CAPTCHA Cloudflare Turnstile** en el registro y la recuperación de contraseña, y en el login a partir del tercer fallo. Falla cerrado.
- **Honeypot** en los formularios públicos.
- **Validadores de contraseña**: mínimo 12 caracteres para el personal y verificación contra filtraciones (HIBP con k-anonimato).
- **Roles** (8 grupos) definidos en `apps/accounts/roles.py`, con los comandos `setup_roles` (idempotente) y `export_permissions_matrix` → [`docs/matriz-permisos.md`](docs/matriz-permisos.md), que el CI verifica.
- **Control de acceso**: `RoleRequiredMixin` (deniega por defecto y falla si una vista no declara permisos), `StaffRequiredMixin` (personal + MFA), `authenticated_user()` y `ensure_segregation_of_duties()`. Querysets filtrados por dueño o sede.
- **MFA obligatorio y cierre por inactividad (15 min) para el personal** (`StaffSecurityMiddleware`). El admin de Django pasa por el login con MFA y es exclusivo del superadmin.
- **Cambio de rol** desde el panel: nadie cambia su propio rol, solo un superadmin gestiona superadmins, se cierran las sesiones del afectado y el ascenso a rol privilegiado genera una alerta.
- **Mi cuenta**: resumen, datos personales (documento y celular **cifrados en reposo** con MultiFernet y *blind index*), direcciones (máximo 10, una predeterminada, protegidas contra IDOR), y privacidad con autorizaciones, **descarga de mis datos** (JSON, con límite de 5 por hora) y **eliminación de la cuenta** con anonimización.
- **Habeas Data**: política de tratamiento de datos y términos versionados (`LegalDocument` v1.0). Al registrarse se guarda la versión aceptada, la IP y el navegador.
- **Panel** (`/panel/`): layout propio con menú según los permisos, resumen, personal y roles, bitácora de auditoría y eventos de seguridad.
- **Auditoría**:
  - `AuditLog` **encadenado por hash SHA-256**, *append-only* en el ORM y con un **trigger de PostgreSQL** que bloquea UPDATE y DELETE;
  - comando `verify_audit_chain`;
  - registro de logins, logouts, registros, cambios de perfil, direcciones, roles, consentimiento, exportación y eliminación de datos.
- **Eventos de seguridad** con alerta por correo a los superadmins (Celery, al confirmar la transacción) en: bloqueo por fuerza bruta, ráfaga de 403 (10 en 5 min), ascenso a rol privilegiado y exportación masiva.
- Departamentos y 51 municipios (códigos DANE DIVIPOLA). Modelo `Store` (sedes) y asignación de personal por sede.
- `seed_demo_users`: un usuario de demostración por rol (solo desarrollo).
- ADR-0012.

### Seguridad
- Deploy checks propios: `byte.E002`/`E003` si faltan las claves de cifrado y `byte.W003` si se usan las claves de prueba de Turnstile.
- Las claves de cifrado se gestionan por entorno y admiten rotación (la primera clave cifra y todas descifran).
- Los logs de Celery usan el `LOGGING` de Django.

### Corregido
- La página "Sesiones activas" devolvía 500: faltaba `django.contrib.humanize`, que usan las plantillas de allauth. Ya tiene test de regresión.
- El contenido de "Mi cuenta" no se mostraba, porque el layout estaba en un `{% include %}`, que no participa en la herencia de bloques. Ahora el layout se hereda y los tests comprueban el contenido de la página, no solo el código 200.

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
