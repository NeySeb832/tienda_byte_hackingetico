# CLAUDE.md — Byte

Guía de trabajo para Claude y para cualquier persona que desarrolle en este repositorio.
Mantener actualizada: si cambia una convención, un comando o una decisión, se actualiza aquí en el mismo commit.

## Proyecto

**Byte** es la tienda en línea y punto de venta de una cadena de videojuegos, consolas y accesorios en
Colombia: precios en COP, IVA 19 % y envíos nacionales por departamento y ciudad. Es un monolito
modular Django con:

- una tienda para clientes,
- un panel propio (`/panel/`),
- una API REST versionada (`/api/v1/`),
- un módulo de Big Data / BI (`/panel/analytics/`).

Es un proyecto académico de **Hacking ético**. La seguridad (OWASP Top 10:2025) es un requisito de
primer nivel, no un añadido.

## Reglas de trabajo (obligatorias)

1. **Fases**: se trabaja por las fases de la tabla de abajo. Al cerrar cada fase se sigue este orden:
   tests, linters y análisis de seguridad → `CHANGELOG.md` → bitácora con capturas → commit
   convencional → **detenerse para revisión**.
2. **Ramas**: cada fase vive en `fase/NN-nombre` y se fusiona a `main` solo cuando el usuario la aprueba.
3. **Commits convencionales**: `feat:`, `fix:`, `sec:`, `docs:`, `test:`, `refactor:`, `chore:`, `ci:` y `build:`.
4. **Secretos**: nunca en el código ni en el repositorio. Todo va por variables de entorno
   (`.env.example` documentado y `.env` ignorado por git).
5. **Decisiones**: cuando haya varias opciones razonables, se elige la más simple y segura y se
   documenta como ADR en `docs/adr/`.
6. **Versiones**: antes de fijar una librería o un servicio se verifica su versión estable vigente y
   cualquier cambio se anota en el ADR-0005 o en el CHANGELOG.
7. **Idioma**: código, nombres de modelos y comentarios en **inglés**; interfaz, mensajes al usuario y
   documentación en **español**.
8. **Tests**: todo cambio de lógica de negocio lleva tests. La meta es una cobertura ≥ 80 % en `services.py`.
9. **Evidencias** (ADR-0010): cada avance se documenta en `docs/bitacora/fase-NN.md` con las secciones
   *Qué · Cómo · Por qué · Evidencias · Pendientes*. Las capturas van en `docs/capturas/fase-NN/` y se
   muestran también en el chat al cerrar la fase.

## Estado de las fases

| # | Fase | Estado |
|---|------|--------|
| 1 | Fundaciones (estructura, settings, Docker, CI, ADRs, modelo de datos) | ✅ en revisión (`fase/01-fundaciones`) |
| 2 | Usuarios y seguridad base (allauth + MFA, axes, roles, mixins, auditoría, CSP, tests de acceso) | ✅ en revisión (`fase/02-usuarios-seguridad`) |
| 3 | Catálogo y precios (variantes con precio dinámico, búsqueda, filtros, comparador, historial) | ✅ en revisión (`fase/03-catalogo`) |
| 4 | Carrito, checkout y pagos (cupones, envíos, Wompi sandbox, webhooks, facturas PDF, correos) | ✅ en revisión (`fase/04-checkout`) |
| 5 | Panel administrativo (dashboard, inventario multi-sede, compras, pedidos, POS, CRM, reportes) | ✅ en revisión (`fase/05-panel`) |
| 6 | Valor agregado (retomas, servicio técnico, fidelidad, preventas, alertas, devoluciones) | ✅ en revisión (`fase/06-valor-agregado`) |
| 7 | Big Data / BI (seed masivo, pipeline medallón, modelo estrella, modelos, dashboards, PySpark) | ✅ en revisión (`fase/07-bigdata`) |
| 8 | Endurecimiento de seguridad (matriz OWASP, STRIDE, suite de seguridad, ZAP, SBOM) | ✅ en revisión (`fase/08-seguridad`) |
| 9 | Despliegue (Render Blueprint, CI/CD, datos demo, verificación end-to-end) | ✅ en revisión (`fase/09-despliegue`) |
| 10 | Documentación final (README, manuales por rol, manual técnico, guion de sustentación) | ✅ en revisión (`fase/10-documentacion`) |

## Arquitectura

- **Monolito modular** con capa de servicios (ADR-0001). La lógica de negocio **no** vive en las vistas.
  - `services.py`: casos de uso que escriben. Son transaccionales, validan reglas de negocio y registran auditoría.
  - `selectors.py`: consultas de lectura, con `select_related`/`prefetch_related` y querysets ya
    filtrados por el usuario o la sede.
  - `views.py`, `forms.py` y los serializers solo orquestan HTTP: validan la entrada, llaman a un
    servicio o selector y renderizan.
  - `permissions.py`: reglas de acceso de la app (ADR-0003).
- Apps en `apps/`: `core` (base transversal), `panel` (carcasa de `/panel/`), `accounts`, `catalog`,
  `pricing`, `inventory`, `purchasing`, `cart`, `orders`, `payments`, `shipping`, `promotions`,
  `tradein`, `services_desk`, `reviews`, `pos`, `notifications`, `cms`, `audit`, `analytics` y `api`.
- Cada app tiene `models.py`, `services.py`, `selectors.py`, `forms.py`, `views.py`, `permissions.py`,
  `migrations/` y `tests/`. `tests/test_structure.py` hace cumplir esta estructura.
- Configuración por entorno: `config/settings/{base,dev,test,prod}.py` con `django-environ`.
- Asíncrono con Celery y Celery Beat sobre Valkey/Redis, serializando **solo JSON** (ADR-0009).

## Convenciones de dominio y seguridad

- **Identificadores**: la PK interna es `bigint` y nunca sale a URLs, plantillas ni API. Hacia afuera
  se exponen `public_id` (UUID4) o `slug` (ADR-0011). Los modelos heredan de
  `apps.core.models.PublicIdModel` y `TimeStampedModel`.
- **Dinero**: `DecimalField(max_digits=14, decimal_places=2)` en COP. Nunca `float`
  (`apps.core.money.to_money` lo rechaza). Los precios del catálogo **incluyen IVA**. El desglose se
  hace con `split_vat()` y el redondeo es `ROUND_HALF_UP` (ADR-0004).
- **Inventario**: los cambios de stock se hacen siempre en `transaction.atomic()` con
  `select_for_update()`, bloqueando en orden de PK para evitar deadlocks. Hay constraints `CHECK` en la BD.
- **Registros append-only**: el kardex (`StockMovement`), la línea de tiempo de los pedidos, los ledgers de puntos y de crédito, el historial de precios
  (`PriceHistory`, con trigger en la BD) y la auditoría solo se agregan; las correcciones se hacen con movimientos inversos.
- **Precios**: cambian solo con `apps.pricing.services` (manual, recálculo por modificadores o
  cambio programado aplicado por Beat). El precio tachado solo aparece tras una bajada real en
  los últimos 30 días y es el más bajo de los 30 días previos (ADR-0013).
- **Catálogo**: las variantes se crean con `catalog.services.create_variant` (una opción por
  atributo, sin combinaciones repetidas). Después de cambiar nombres, plataformas o variantes se
  llama a `refresh_search_index`. Las listas del visitante (comparador, vistos) guardan solo
  `public_id` en la sesión.
- **Checkout y pagos** (ADR-0014): el pedido se crea con `orders.services.place_order`, que
  recalcula precios, cupón y envío en el servidor y reserva stock todo o nada. Los estados solo
  cambian con `orders.services.transition`. Un pago se aplica solo con firma válida, referencia
  existente y monto exacto; si no, se rechaza y se registra un evento de seguridad. La URL de
  retorno de la pasarela nunca decide el estado. `BYTE_PAYMENT_GATEWAY=fake` usa el simulador.
- **Panel** (ADR-0015): las vistas operativas viven en `apps/panel/operations.py`, declaran
  `required_permissions` y filtran todo por `stores_for(user)` (objeto de otra sede → 404). El POS
  vende con `pos.services.sell` (pedido canal `pos`, misma reserva y kardex que la web). Los CSV se
  generan con `analytics.selectors.to_csv`, que neutraliza fórmulas.
- **Puntos y saldo** (ADR-0016): solo con `promotions.services` (`award_points`, `redeem_points`,
  `add_credit`, `spend_credit`), que agregan filas a libros append-only bajo bloqueo por usuario.
  Las devoluciones van por `orders.returns` (plazos de Ley 1480) y las alertas por
  `notifications.services` (se envían una sola vez, después del commit).
- **Snapshots**: los pedidos copian precio, nombre, SKU y dirección. Cambiar el catálogo no altera un pedido.
- **Control de acceso**: se deniega por defecto. Toda vista del panel exige autenticación y un permiso
  explícito a través de los mixins propios. Los querysets se filtran por dueño o sede (anti-IDOR).
  - Vistas del panel: heredan de `StaffRequiredMixin` y declaran `required_permissions`. Si no los
    declaran, falla con `ImproperlyConfigured`.
  - Vistas de cliente: usan `LoginRequiredMixin` y obtienen el usuario con `authenticated_user(request)`.
    Los objetos ajenos se cargan con selectors que responden 404.
  - Los roles y sus permisos solo se definen en `apps/accounts/roles.py`. Después de cambiarlos se
    ejecutan `setup_roles` y `export_permissions_matrix`; el CI verifica que la matriz esté al día.
- **Auditoría**: toda operación relevante llama a `apps.audit.services.record_event(...)`. Los
  incidentes usan `record_security_event(...)`, que alerta a los superadmins por correo en los casos
  graves. La bitácora es inmutable: tiene un trigger en la BD y se verifica con `verify_audit_chain`.
- **Datos sensibles**: van en `EncryptedTextField` (`apps.core.crypto`). Para buscarlos se usa un
  *blind index*; nunca se filtra sobre el campo cifrado.
- **Separación de funciones**: quien crea un ajuste, un descuento alto, un reembolso o una orden de
  compra no puede aprobarlo. Se valida en el servicio y con `CHECK` en la BD (ajustes, órdenes de
  compra, cupones, devoluciones y reembolsos).
- **Plantillas**: autoescapado siempre. Está prohibido `|safe` y `mark_safe` sobre datos de usuario;
  el HTML de usuarios se sanitiza con `nh3`.
- **CSP estricta con nonce**: todo `<script>` lleva `nonce="{{ request.csp_nonce }}"`. No se permiten
  scripts ni estilos inline sin nonce ni handlers `on*=`. Alpine se usa en su **versión CSP**: los
  componentes se registran con `Alpine.data()` en `static/js/app.js` (ADR-0006).
- **HTMX**: el token CSRF viaja en la cabecera `X-CSRFToken` (`hx-headers` en `<body>`).
- **Validación**: siempre en el servidor. La validación en el cliente es solo ayuda.
- **Logs**: JSON estructurado con `request_id`. Nunca se registran contraseñas, tokens, documentos ni
  datos de tarjeta; `apps.core.logging.SensitiveDataFilter` enmascara las claves sensibles.
- **Errores**: el usuario ve un mensaje genérico con el ID de correlación (`X-Request-ID`). El detalle
  va solo al log. Ante cualquier fallo de permisos, pasarela o antifraude, se falla cerrado.

## Interfaz y catálogo (indicaciones del usuario)

- **Producto real:** la interfaz nunca menciona fases, el proyecto académico ni estados de
  desarrollo. Los avisos obligatorios (pagos en sandbox, factura de prueba) aparecen solo donde la
  especificación lo exige: en el checkout y en la factura.
- **Inicio como tienda en línea completa:**
  - barra de anuncios;
  - slider con consolas, accesorios y servicios;
  - beneficios;
  - categorías con imagen;
  - productos destacados;
  - retoma, servicio técnico con precios, marcas y un pie de página completo.

  Un test (`test_home_page_reads_like_a_real_store`) evita que vuelvan las referencias a fases.
- **Fotos reales de producto con licencia libre** (dominio público, CC0, CC BY o CC BY-SA) tomadas
  de Wikimedia Commons:
  - `scripts/product_images.py` fija el SHA-256 del original, rechaza licencias no libres, quita el
    fondo de estudio y genera WebP sin EXIF en `static/img/productos/`;
  - los créditos se publican en `/creditos-imagenes/`.

  Nunca se usan imágenes sin licencia verificable.
- **Precios:** la referencia es la lista maestra del negocio (`Lista_Precios_ByteMarket_MAESTRO.xlsx`,
  valores en COP con IVA). Una lista secundaria sirve de respaldo, con valores en miles (`$ 2'650` =
  $ 2.650.000).
  - Se **excluyen** las consolas "programadas" o "copia" y los servicios de chip o liberación de
    juegos, porque implican software sin licencia.
  - No se inventan descuentos "antes/ahora" sin un precio anterior real (Ley 1480).
- **Contenido del inicio:** las categorías y los productos destacados salen de la BD
  (`catalog/selectors.py`). Los slides (`cms/selectors.py`) y los servicios técnicos
  (`services_desk/selectors.py`) siguen estáticos hasta que existan sus modelos.
- **Datos demo:** `seed_demo` carga `apps/catalog/demo_data.py` (66 productos de la lista maestra,
  sin consolas programadas ni copias). Los juegos usan precios de referencia porque ninguna lista
  los trae.

## Comandos

En este equipo (Windows) `uv` se instaló con pip: si no está en el PATH, se antepone `py -m`
(por ejemplo, `py -m uv run pytest`).

```bash
# Entorno
uv sync                                   # instala dependencias desde uv.lock (incluye grupos dev y security)
cp .env.example .env                      # luego completar secretos (ver docs/despliegue.md)

# Infraestructura local (Docker Desktop)
docker compose up -d db redis             # solo PostgreSQL y Valkey (para correr Django en el host)
docker compose up --build                 # stack completo: web, worker, beat, db, redis, tailwind

# Django
uv run python manage.py migrate
uv run python manage.py runserver
uv run python manage.py tailwind build    # compila Tailwind (CLI standalone, sin Node)
uv run python manage.py tailwind watch    # recompila al guardar
uv run python manage.py createsuperuser

# Celery
uv run celery -A config worker -l INFO
uv run celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Calidad
uv run pytest                             # tests (config en pyproject.toml)
uv run pytest --cov                       # con cobertura
uv run ruff check .                       # linter
uv run black --check .                    # formato
uv run mypy .                             # tipos (gradual)

# Seguridad
uv run bandit -c pyproject.toml -r apps config
uv run pip-audit                          # vulnerabilidades en dependencias
DJANGO_SETTINGS_MODULE=config.settings.prod uv run python manage.py check --deploy   # requiere env de prod
uv run python scripts/evidencia.py --fase 8 --solo sbom                              # SBOM → docs/seguridad/sbom.cdx.json
BYTE_ZAP_TARGET=http://host.docker.internal:8001 uv run python scripts/evidencia.py --fase 8 --solo zap  # ZAP baseline

# Dependencias (ADR-0005)
uv add "paquete>=X,<Y"                    # nunca pip install suelto
uv lock --check                           # el lock está al día
uv export --frozen --no-default-groups --no-emit-project --format requirements-txt -o requirements/prod.txt   # solo dependencias de la app
uv export --frozen --no-default-groups --group dev --no-emit-project --format requirements-txt -o requirements/dev.txt

# Evidencias (ADR-0010)
uv run python scripts/evidencia.py --fase 1      # tests, linters y seguridad → SVG + TXT
uv run python scripts/capturas.py --fase 1       # pantallas con Playwright → JPG
uv run python scripts/vendor_assets.py --check   # verifica la integridad de las librerías JS servidas localmente
uv run python scripts/product_images.py --bloquear  # fija SHA-256 y licencia de fotos nuevas (assets/img/productos.json)
uv run python scripts/product_images.py            # descarga, verifica y genera los WebP + créditos
```

```bash
# Fase 2
uv run python manage.py setup_roles                  # grupos y permisos (idempotente)
uv run python manage.py export_permissions_matrix    # docs/matriz-permisos.md (--check en CI)
uv run python manage.py verify_audit_chain           # integridad de la bitácora de auditoría
uv run python manage.py seed_demo_users              # un usuario demo por rol (solo DEBUG)

# Fase 3
uv run python manage.py seed_demo                    # catálogo demo, sedes y stock (idempotente)
```

Fase 7: `seed_bigdata` (histórico sintético + lago) y `run_pipeline` (reconstruye plata y oro).
Fase 9: `bootstrap_demo` (demo completa), `scripts/backup.py` (respaldar, verificar y restaurar) y
`scripts/e2e.py` (compra de extremo a extremo con Playwright). Guía: `docs/despliegue.md`.

## Dependencias

- Se gestionan con `uv`: `uv.lock` incluye hashes y `[tool.uv] exclude-newer = "7 days"` impone una
  **cuarentena de 7 días** contra paquetes recién publicados (ADR-0005).
- Docker y Render instalan desde `requirements/*.txt`, exportados del lock con hashes
  (`pip install --require-hashes`). Si cambia el lock, se regeneran en el mismo commit; el CI lo verifica.
- Las dependencias se agregan **en la fase que las usa**, con la versión aprobada en la propuesta
  inicial o con la estable vigente, verificada en ese momento.
- Las librerías JS (htmx, Alpine CSP y más adelante ECharts) se sirven localmente desde
  `static/vendor/` con su integridad verificada por `scripts/vendor_assets.py`. No se usan CDNs.
- Las imágenes Docker y las GitHub Actions se fijan por digest o SHA.

## Decisiones (ADR)

Índice en [`docs/adr/README.md`](docs/adr/README.md). Las más relevantes son:

- 0001: monolito modular
- 0002: Django 5.2 LTS + django-csp
- 0003: permisos de objeto propios
- 0004: dinero e IVA
- 0005: uv, hashes y cuarentena
- 0006: frontend sin Node con Alpine CSP
- 0007: Wompi detrás de `PaymentGateway`
- 0008: el checkout exige cuenta
- 0009: Celery con JSON y Valkey
- 0010: bitácora con capturas
- 0011: identificadores públicos y usuario por email
- 0012: autenticación con allauth, axes, Turnstile y HIBP
- 0013: búsqueda en PostgreSQL y precios con historial
- 0014: checkout con reserva de stock y pagos que fallan cerrado
- 0015: panel con separación de funciones y alcance por sede
- 0016: puntos y saldo append-only; reembolsos con aprobación de otra persona

## Parámetros de negocio por defecto

Son configurables por entorno y, más adelante, desde el panel:

- Un descuento mayor a **15 %** requiere aprobación de otra persona (`BYTE_HIGH_DISCOUNT_APPROVAL_PCT`).
- La reserva de stock del carrito dura **15 min** (`BYTE_STOCK_RESERVATION_TTL_MINUTES`).
- Devoluciones: retracto de 5 días hábiles (Ley 1480) y una ventana comercial de 30 días.
- Contraseñas: mínimo 12 caracteres para el personal y 10 para clientes, con verificación HIBP en la F2.

## Entorno local conocido

- Windows 11 con Python 3.12 (`py`) y uv vía `py -m uv`.
- Docker Desktop 29 con WSL2 (instalado y verificado). Si `docker` no está en el PATH de Git Bash:
  `export PATH="$PATH:/c/Program Files/Docker/Docker/resources/bin"`.
- `.gitattributes` fuerza finales de línea LF para que los scripts funcionen dentro de los contenedores.
