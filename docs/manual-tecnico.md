# Manual técnico

## Arquitectura
Monolito modular Django (ADR-0001) con 21 apps. Cada app separa `services.py` (escritura
transaccional + auditoría), `selectors.py` (lectura con alcance), vistas delgadas y
`permissions.py`. Configuración por entorno en `config/settings/` y convenciones en
[`CLAUDE.md`](../CLAUDE.md).

| Dominio | Apps | Piezas clave |
|---------|------|--------------|
| Identidad | `accounts`, `audit` | allauth + MFA, axes, roles en `roles.py`, auditoría encadenada por hash |
| Catálogo y precios | `catalog`, `pricing` | variantes con `combination_key`, búsqueda FTS + trigramas, historial de precios inmutable |
| Venta | `cart`, `orders`, `payments`, `shipping`, `promotions` | `place_order` (reserva todo o nada), máquina de estados, `PaymentGateway` (Wompi/simulador), webhooks idempotentes |
| Operación | `inventory`, `purchasing`, `pos`, `panel` | kardex, ajustes y compras con SoD, POS sobre el mismo flujo de pedidos |
| Valor agregado | `tradein`, `services_desk`, `notifications`, `orders.returns` | libros de puntos y saldo, tickets, alertas, RMA |
| BI | `analytics` | DuckDB + Parquet (bronce/plata/oro), RFM, pronóstico, ECharts |

## Datos
Modelo en [`modelo-datos.md`](modelo-datos.md). Invariantes en la BD:
- `CHECK` de cantidades, montos y separación de funciones;
- triggers append-only (auditoría, precios, kardex, puntos, saldo, líneas de tiempo);
- secuencias para numerar pedidos, facturas y órdenes de compra.

## Asíncrono (Celery, solo JSON)
| Tarea | Cuándo |
|-------|--------|
| `pricing.apply_scheduled_price_changes` | cada 5 min |
| `orders.expire_unpaid_orders` | cada 5 min |
| `analytics.run_pipeline` | 3:00 a. m. |
| Correos de pedido y servicio técnico, alertas de producto, alertas de seguridad | al confirmar la transacción |

## Operación
- Comandos: `setup_roles`, `export_permissions_matrix`, `verify_audit_chain`, `seed_demo`,
  `seed_demo_users`, `seed_bigdata`, `run_pipeline`, `bootstrap_demo`.
- Respaldos: `scripts/backup.py`. Despliegue: [`despliegue.md`](despliegue.md).
- Evidencias: `scripts/evidencia.py --fase N` (14 chequeos + ZAP) y `scripts/capturas.py`.

## Seguridad
[Matriz OWASP Top 10:2025](seguridad/owasp-top10-2025.md), [STRIDE](seguridad/stride.md),
[SBOM](seguridad/sbom.cdx.json) e [informe ZAP](seguridad/zap-baseline.html).
