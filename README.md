# Byte — videojuegos, consolas y accesorios

Byte es la tienda en línea y el punto de venta de una cadena colombiana de videojuegos, consolas y
accesorios: precios en COP con IVA incluido, envíos por departamento y ciudad, retomas, servicio
técnico, fidelidad y un módulo de Big Data / BI para la gerencia.

> **Proyecto académico (Hacking ético).** La seguridad sigue el OWASP Top 10:2025
> ([matriz](docs/seguridad/owasp-top10-2025.md), [STRIDE](docs/seguridad/stride.md)). Los pagos
> funcionan en sandbox y las facturas son documentos de prueba.

**Estado:** las 10 fases completas. Ver [`CHANGELOG.md`](CHANGELOG.md) y la
[bitácora con evidencias](docs/bitacora/).

## Qué incluye
- **Tienda:** catálogo con variantes y precio dinámico, búsqueda tolerante a errores, filtros con
  facetas, comparador, carrito de invitado, checkout con envíos por zona o recogida, cupones,
  pagos Wompi (sandbox) o simulador, factura PDF de prueba, puntos, saldo a favor, retomas,
  servicio técnico, alertas de stock y precio, devoluciones (Ley 1480) y preventas.
- **Panel:** pedidos, inventario multi-sede con kardex, ajustes y traslados, compras, punto de
  venta con arqueo, clientes, precios, cupones, retomas, servicio técnico, devoluciones, reportes,
  BI, personal, auditoría y eventos de seguridad. Todo con separación de funciones y alcance por sede.
- **BI:** lago de datos medallón con DuckDB, modelo estrella, RFM, pronóstico y tablero ECharts.

## Stack
Python 3.12 · Django 5.2 LTS · PostgreSQL 17 · Valkey 8 · Celery + Beat · HTMX · Alpine CSP ·
Tailwind 4 (sin Node) · DuckDB · ECharts · ReportLab · `uv` (lock con hashes y cuarentena de 7 días) ·
Docker multi-etapa (no root) · GitHub Actions · bandit · semgrep · pip-audit · Trivy · ZAP · SBOM.
Decisiones en [`docs/adr/`](docs/adr/README.md) (17 ADR).

## Puesta en marcha (desarrollo)
Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/) y Docker Desktop.

```bash
uv sync
cp .env.example .env                           # completar secretos (ver comentarios del archivo)
uv run python scripts/vendor_assets.py         # htmx, Alpine CSP, ECharts y Tailwind verificados
docker compose up -d db redis
uv run python manage.py migrate
uv run python manage.py bootstrap_demo         # roles, catálogo, usuarios demo y BI
uv run python manage.py tailwind build
uv run python manage.py runserver              # http://127.0.0.1:8000
```

Stack completo en contenedores: `docker compose up --build`.

## Usuarios de demostración
Contraseña: `BYTE_DEMO_PASSWORD` de tu `.env`. El personal entra con MFA. En desarrollo
(`DEBUG=True`) usa el TOTP de demostración de `seed_demo_users`; en cualquier otro entorno, como
Render, cada cuenta del personal activa su propio autenticador en el primer ingreso.

| Rol | Correo | Qué puede hacer |
|-----|--------|-----------------|
| Cliente | `cliente@byte.test` | Comprar, retomas, puntos, devoluciones, servicio técnico |
| Vendedor / Cajero | `vendedor@byte.test` | POS, pedidos, recibir devoluciones y equipos |
| Bodeguero | `bodega@byte.test` | Inventario, ajustes (sin aprobar), traslados, recepciones |
| Técnico de soporte | `tecnico@byte.test` | Servicio técnico y evaluación de retomas |
| Gerente de tienda | `gerente@byte.test` | Todo lo operativo y las aprobaciones |
| Analista de datos | `analista@byte.test` | Reportes y BI |
| Administrador | `admin@byte.test` | Todo lo anterior y gestión de personal |
| Superadmin | `superadmin@byte.test` | Además, eventos de seguridad y admin de Django |

## Calidad y seguridad
```bash
uv run pytest -n 4                                   # 724 tests
uv run python scripts/evidencia.py --fase 10         # tests, linters, SAST, SCA, Trivy, SBOM (y ZAP con BYTE_ZAP_TARGET)
uv run python scripts/e2e.py --base-url http://127.0.0.1:8000
```

## Documentación
- [Manuales por rol](docs/manuales/) · [Manual técnico](docs/manual-tecnico.md) ·
  [Despliegue en Render](docs/despliegue.md) · [Modelo de datos](docs/modelo-datos.md) ·
  [Matriz de permisos](docs/matriz-permisos.md) · [Guion de sustentación](docs/sustentacion.md)
