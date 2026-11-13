# Bitácora · Fase 5 — Panel administrativo

- **Rama:** `fase/05-panel`
- **Fecha:** 2026-11-13
- **Estado:** ✅ en revisión

## 1. Qué se hizo

- Resumen con indicadores por rol.
- Pedidos: listado, filtros, detalle y cambios de estado de preparación y entrega.
- Inventario multi-sede: existencias, kardex, ajustes con aprobación y traslados entre sedes.
- Compras: proveedores, órdenes de compra con aprobación y recepciones parciales.
- Punto de venta con turnos de caja, efectivo o datáfono y arqueo al cierre.
- Clientes (CRM), precios, cupones y reportes con exportación CSV.

## 2. Cómo se hizo

- **Servicios nuevos:** `inventory.services` (`move_stock`, ajustes y traslados),
  `purchasing.services` (crear, aprobar y recibir) y `pos.services` (abrir y cerrar turno, vender).
  Todos son transaccionales, bloquean filas con `select_for_update` y registran auditoría.
- **POS sobre el mismo flujo que la web:** una venta en mostrador crea un pedido canal `pos`,
  reserva en la sede del turno, registra el pago (efectivo o datáfono), consume la reserva (kardex
  "Venta"), pasa a pagado y entregado, y emite la factura de prueba.
- **Vistas:** `apps/panel/operations.py`. Cada una declara `required_permissions` y parte de las
  sedes asignadas al usuario; los formularios solo ofrecen esas sedes.
- **Permisos:** nuevos permisos de modelo (`request_adjustment`, `approve_adjustment`,
  `manage_transfers`, `approve_purchaseorder`, `receive_purchaseorder`, `use_pos`,
  `manage_fulfillment`, `view_sales_report`, `change_price`, `approve_coupon`) asignados en
  `roles.py`; `setup_roles` y `export_permissions_matrix` regeneraron la matriz.
- **Reportes:** consultas agregadas con `TruncDate`, gráfica en SVG con atributos (sin estilos en
  línea, por la CSP) y CSV con celdas neutralizadas.
- **Capturas:** `scripts/capturas.py` prepara datos de demostración (turno de caja con ventas,
  ajuste y orden de compra pendientes, traslado) antes de abrir el navegador.

### Problemas encontrados y cómo se resolvieron

| Problema | Solución |
|----------|----------|
| El indicador "stock bajo" contaba filas por sede (167) | Ahora cuenta productos con ≤ 2 unidades libres sumando las sedes del usuario |
| Aviso del navegador: el campo de fecha de cupones no tenía formato `datetime-local` | El widget usa `%Y-%m-%dT%H:%M` |
| Un test esperaba 404 en un traslado ajeno, pero el vendedor no tiene ese permiso (403) | El test usa el rol de bodega; el 403 era el comportamiento correcto |
| El test de límite de tasa podía fallar si las peticiones cruzaban el cambio de minuto | Hace 121 peticiones y verifica que aparezca un 403 |
| `operations.py` quedó con 65 % de cobertura | Tests de cada vista con datos: 89 % |

## 3. Por qué

- **Separación de funciones** (ADR-0015): un ajuste, una orden de compra o un descuento alto
  necesitan dos personas, y la base de datos lo garantiza aunque alguien salte el servicio.
- **404 fuera del alcance:** no se revela la existencia de pedidos, traslados u órdenes de otra
  sede (anti-IDOR, OWASP A01).
- **Un solo camino para el stock:** el POS, la web, las compras y los traslados escriben en el
  mismo kardex, así las existencias siempre se pueden reconstruir y auditar.
- **Ficha de cliente auditada:** quién consultó datos personales y cuándo (Ley 1581).
- **CSV sin fórmulas:** un nombre de producto como `=HYPERLINK(...)` no se ejecuta al abrir el
  reporte en Excel.

## 4. Evidencias

El resumen está en [`00-resumen.svg`](../capturas/fase-05/00-resumen.svg).

| # | Verificación | Resultado |
|---|--------------|-----------|
| 01 | Tests (BD recién creada, clon limpio) | ✅ **679 pasan**, cobertura **94 %** |
| 02–04 | ruff · black · mypy | ✅ (mypy falló en la 1.ª corrida por un import en un test; corregido) |
| 05–09, 12–13 | bandit, pip-audit, check --deploy, cabeceras, vendor, matriz, auditoría | ✅ |
| 10 | semgrep | ✅ **0 hallazgos** en 152 reglas (la 1.ª corrida dio 2: un `redirect` con `request.path`; corregido) |
| 11 | Trivy | ✅ 0 HIGH/CRITICAL corregibles |

Al repetir las pruebas en un clon limpio apareció que `apps/cms/data/imagenes.json` estaba
excluido por la regla `data/` del `.gitignore`: se corrigió (`/data/`) y se versionó el archivo.

Tests nuevos: ajustes con separación de funciones (servicio y `CHECK`), traslados con kardex,
órdenes de compra con recepción parcial, POS con cambio y arqueo, CSV sin fórmulas, **matriz de
11 pantallas × 7 roles del personal** (77 casos) más clientes, alcance por sede (stock, pedidos y
traslados de otra sede → 404), cambios de estado inválidos, auditoría de la ficha de cliente y
flujos de cada vista.

### Pantallas (Playwright, usuarios demo por rol)

Consola del navegador: **0 violaciones de CSP**; el único mensaje es el 403 esperado del analista
intentando abrir el POS ([`consola-navegador.txt`](../capturas/fase-05/consola-navegador.txt)).

| Pantalla | Captura |
|----------|---------|
| Resumen del gerente | [claro](../capturas/fase-05/panel-resumen-gerente-escritorio-claro.jpg) · [móvil](../capturas/fase-05/panel-resumen-gerente-movil-oscuro.jpg) |
| Pedidos y detalle | [lista](../capturas/fase-05/panel-pedidos-escritorio-oscuro.jpg) · [detalle](../capturas/fase-05/panel-detalle-pedido-escritorio-oscuro.jpg) |
| Inventario y kardex | [inventario](../capturas/fase-05/panel-inventario-escritorio-oscuro.jpg) · [kardex](../capturas/fase-05/panel-kardex-escritorio-oscuro.jpg) |
| Ajustes: el gerente aprueba, bodega no | [gerente](../capturas/fase-05/panel-ajustes-gerente-aprueba-escritorio-oscuro.jpg) · [bodega](../capturas/fase-05/panel-ajustes-bodega-no-aprueba-escritorio-oscuro.jpg) |
| Traslados | [captura](../capturas/fase-05/panel-traslados-escritorio-oscuro.jpg) |
| Compras y orden por aprobar | [lista](../capturas/fase-05/panel-compras-escritorio-oscuro.jpg) · [orden](../capturas/fase-05/panel-orden-de-compra-escritorio-oscuro.jpg) |
| Punto de venta | [oscuro](../capturas/fase-05/panel-pos-escritorio-oscuro.jpg) · [móvil](../capturas/fase-05/panel-pos-movil-claro.jpg) |
| Clientes, precios y cupones | [clientes](../capturas/fase-05/panel-clientes-escritorio-oscuro.jpg) · [precios](../capturas/fase-05/panel-precios-escritorio-oscuro.jpg) · [cupones](../capturas/fase-05/panel-cupones-escritorio-oscuro.jpg) |
| Reportes (analista) | [oscuro](../capturas/fase-05/panel-reportes-escritorio-oscuro.jpg) · [móvil](../capturas/fase-05/panel-reportes-movil-claro.jpg) |
| 403: el analista no puede usar el POS | [captura](../capturas/fase-05/403-analista-en-pos-escritorio-oscuro.jpg) |

## 5. Pendientes y riesgos

- Devoluciones en mostrador, reembolsos y RMA llegan en la Fase 6.
- Los reportes son operativos; el modelo analítico (estrella, pipeline y dashboards con ECharts)
  es la Fase 7.
- El catálogo (crear productos y variantes) sigue en el admin del superadmin; un editor propio
  en el panel queda para cuando se priorice.
