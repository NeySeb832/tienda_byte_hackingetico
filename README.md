# Byte — videojuegos, consolas y accesorios

Byte es la tienda en línea y el punto de venta de una cadena colombiana de videojuegos, consolas y
accesorios: precios en COP con IVA incluido, envíos por departamento y ciudad, retomas, servicio
técnico y un módulo de Big Data / BI para la gerencia.

> **Proyecto académico (Hacking ético).** La seguridad sigue el OWASP Top 10:2025. Los pagos funcionan
> en modo sandbox y las facturas son documentos de prueba.

**Estado:** Fase 1 de 10 (Fundaciones). Ver [`CHANGELOG.md`](CHANGELOG.md) y [`docs/bitacora/`](docs/bitacora/).

## Stack

- Python 3.12 y Django 5.2 LTS, con Django REST Framework.
- PostgreSQL 17 con `pg_trgm` y Valkey 8, compatible con Redis.
- Celery y Celery Beat.
- Plantillas Django, HTMX, Alpine.js en versión CSP y Tailwind CSS 4, compilado con su CLI standalone, sin Node.
- `uv` para las dependencias, con lock con hashes y una cuarentena de 7 días.
- Docker multi-etapa con usuario no root, GitHub Actions, bandit, semgrep, pip-audit, Trivy y un SBOM CycloneDX.

Las decisiones de arquitectura están en [`docs/adr/`](docs/adr/README.md).

## Puesta en marcha (desarrollo)

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/) y Docker Desktop.

```bash
uv sync                                        # dependencias desde uv.lock
cp .env.example .env                           # completa DJANGO_SECRET_KEY, POSTGRES_PASSWORD y DATABASE_URL
uv run python scripts/vendor_assets.py         # descarga y verifica htmx, Alpine CSP y Tailwind
docker compose up -d db redis                  # PostgreSQL y Valkey
uv run python manage.py migrate
uv run python manage.py tailwind build
uv run python manage.py runserver              # http://127.0.0.1:8000
```

También puedes levantar todo el stack en contenedores (web, worker, beat, db, redis y tailwind):

```bash
docker compose up --build
```

Usuarios de demostración (solo desarrollo; la contraseña se define en `BYTE_DEMO_PASSWORD` de tu `.env`):

```bash
uv run python manage.py seed_demo_users
```

| Rol | Correo |
|-----|--------|
| Cliente | `cliente@byte.test` |
| Vendedor / Cajero | `vendedor@byte.test` |
| Bodeguero | `bodega@byte.test` |
| Técnico de soporte | `tecnico@byte.test` |
| Gerente de tienda | `gerente@byte.test` |
| Analista de datos | `analista@byte.test` |
| Administrador | `admin@byte.test` |
| Superadmin | `superadmin@byte.test` |

El personal entra con MFA. El secreto TOTP de demostración, que es público y solo para desarrollo,
es `JBSWY3DPEHPK3PXP`: agrégalo a tu app de autenticación (Google Authenticator, Aegis, 1Password…).

Pruebas y calidad:

```bash
uv run pytest --cov
uv run ruff check . && uv run black --check . && uv run mypy .
uv run python scripts/evidencia.py --fase 1    # evidencias (SVG y TXT) en docs/capturas/
```

La lista completa de comandos y convenciones está en [`CLAUDE.md`](CLAUDE.md).

## Estructura

```
config/          settings por entorno (base, dev, test, prod), urls, celery, wsgi y asgi
apps/            una app por dominio, cada una con models, services, selectors, forms, views, permissions y tests
templates/       layout base, componentes y páginas de error
static/          js propio y vendor/ (librerías verificadas por hash)
assets/css/      fuente de Tailwind (se compila a static/css/)
docs/            ADR, modelo de datos, bitácora y capturas
scripts/         vendor_assets, evidencia y capturas
tests/           pruebas transversales (estructura y seguridad)
```

## Documentación

- [Modelo de datos (ER en Mermaid)](docs/modelo-datos.md)
- [Decisiones de arquitectura (ADR)](docs/adr/README.md)
- [Bitácora por fases, con capturas](docs/bitacora/)
- Seguridad (matriz OWASP), modelo de amenazas, Big Data y despliegue: se publican en las fases 7 a 9.
