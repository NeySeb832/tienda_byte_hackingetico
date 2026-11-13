# Bitácora · Fase 4 — Carrito, checkout y pagos

- **Rama:** `fase/04-checkout`
- **Fecha:** 2026-11-13
- **Estado:** ✅ en revisión

## 1. Qué se hizo

- Carrito de invitado y de cliente, con fusión al iniciar sesión y límites por stock y por pedido.
- Checkout con envío por zonas o recogida en tienda, cupones, IVA desglosado y aviso de sandbox.
- Pedidos con número consecutivo, snapshot de líneas y dirección (cifrada), máquina de estados
  y línea de tiempo.
- Reserva de stock sin sobreventa, vencimiento automático y kardex.
- Pasarela Wompi sandbox y simulador interno, webhook idempotente y página de resultado.
- Factura electrónica de prueba en PDF, correo de confirmación y sección "Mis pedidos".

## 2. Cómo se hizo

- **Servicios transaccionales:** `orders.services.place_order` recalcula todo en el servidor
  (precios vigentes, cupón, envío, IVA) y, en la misma transacción, crea el pedido, reserva el
  stock y registra el cupón. `payments.services.apply_result` aplica el resultado de la pasarela
  con el pago bloqueado (`select_for_update`).
- **Stock:** las filas de `StockItem` se bloquean en orden de PK; si falta una unidad de una sola
  línea, no se reserva nada. Aprobado el pago, `consume_reservations` descuenta y escribe el kardex;
  rechazado o vencido, `release_reservations` libera.
- **Wompi:** el enlace al Web Checkout lleva la firma de integridad
  `SHA-256(referencia + monto en centavos + COP + secreto)`; los eventos se verifican recalculando
  el checksum con las propiedades que indica el evento, el timestamp y el secreto de eventos.
- **Simulador:** con `BYTE_PAYMENT_GATEWAY=fake`, el "pago" ocurre en `/pagos/simulador/<ref>/`
  (solo el dueño, solo pagos pendientes), que emite un evento firmado con HMAC y lo procesa por el
  mismo camino que un webhook real.
- **Numeración:** secuencias de PostgreSQL para pedidos y facturas.
- **Correo:** tarea de Celery con argumentos JSON, encolada con `transaction.on_commit`.

### Problemas encontrados y cómo se resolvieron

| Problema | Solución |
|----------|----------|
| Un id de carrito alterado en la sesión causaba error 500 (lo detectó un test) | Se valida como UUID y se ignora si no lo es |
| `check --deploy` advertía el simulador de pagos en los tests de configuración | Esos tests usan `wompi` con llaves de prueba; nuevo test para `byte.E004` |
| El reemplazo automático del ícono del carrito dejó comillas escapadas en la plantilla | Corregido; la prueba de la página del carrito lo cubre |
| Las plantillas de "Mis pedidos" usaban un bloque inexistente | Usan el bloque `content` del layout de la cuenta |
| `cart/services.py` quedó en 76 % de cobertura | Tests de límites, sesión alterada, fusión y cupones: 92 % |

## 3. Por qué

- **Reservar al crear el pedido** (no al agregar al carrito) evita bloquear inventario con
  carritos abandonados y garantiza que dos compras simultáneas no vendan la misma unidad (ADR-0014).
- **Fallar cerrado en pagos:** un webhook falso, una firma incorrecta o un monto distinto nunca
  marcan un pedido como pagado; quedan como eventos de seguridad para revisión (OWASP A04/A08).
- **Mensaje genérico en cupones** y límite de tasa: no se pueden enumerar códigos válidos.
- **Anti-IDOR:** pedidos, facturas, resultado y simulador se consultan siempre filtrando por el
  dueño y responden 404 a cualquier otro.
- **Factura de prueba claramente marcada:** la especificación exige el aviso; no hay integración
  real con la DIAN.

## 4. Evidencias

El resumen está en [`00-resumen.svg`](../capturas/fase-04/00-resumen.svg).

| # | Verificación | Resultado |
|---|--------------|-----------|
| 01 | Tests (pytest) contra PostgreSQL 17 | ✅ **582 pasan** (antes 530), cobertura **94 %** |
| — | Cobertura de los `services.py` de la fase | ✅ 85–97 % (carrito 92 %, pedidos 93 %, pagos 88 %, cupones 97 %) |
| 02–04 | ruff · black · mypy | ✅ |
| 05 | bandit (severidad media o alta) | ✅ 0 hallazgos |
| 06 | pip-audit (con ReportLab 5.1.0) | ✅ sin vulnerabilidades conocidas |
| 07 | `check --deploy` (incluye `byte.E004`/`W004` de pagos) | ✅ |
| 08 | Cabeceras de seguridad | ✅ |
| 09 | Integridad de las librerías JS y Tailwind | ✅ |
| 10 | semgrep `p/django` + `p/python` | ✅ **0 hallazgos** en 152 reglas y 350 archivos |
| 11 | Trivy sobre `byte:local` **reconstruida** con ReportLab | ✅ 0 HIGH/CRITICAL corregibles |
| 12 | Matriz de permisos | ✅ al día |
| 13 | Cadena de auditoría (BD de desarrollo) | ✅ íntegra |

Tests nuevos: flujo completo (pedido, reserva, pago aprobado, rechazado y vencido, kardex,
factura, correo), sobreventa, reserva todo o nada, máquina de estados, envío y recogida, cupones
(límites, vigencia, aprobación por otra persona, `CHECK` en BD), firmas de Wompi (integridad y
eventos, alteración del monto), webhook idempotente, firma inválida, monto distinto, referencia
desconocida o ajena, cuerpo demasiado grande, y vistas (carrito, checkout, simulador, pedidos,
factura PDF, IDOR entre clientes).

### Pantallas (Playwright, usuario demo `cliente@byte.test`)

Consola del navegador: **0 mensajes y 0 violaciones de CSP**
([`consola-navegador.txt`](../capturas/fase-04/consola-navegador.txt)).

| Pantalla | Captura |
|----------|---------|
| Ficha con "Agregar al carrito" | [captura](../capturas/fase-04/ficha-agregar-al-carrito-escritorio-oscuro.jpg) |
| Carrito | [claro](../capturas/fase-04/carrito-escritorio-claro.jpg) · [móvil](../capturas/fase-04/carrito-movil-oscuro.jpg) |
| Checkout con aviso de sandbox | [oscuro](../capturas/fase-04/checkout-escritorio-oscuro.jpg) · [móvil](../capturas/fase-04/checkout-movil-claro.jpg) |
| Pasarela de pruebas | [captura](../capturas/fase-04/pasarela-de-pruebas-escritorio-oscuro.jpg) |
| Pago aprobado | [captura](../capturas/fase-04/pago-aprobado-escritorio-oscuro.jpg) |
| Pago rechazado | [captura](../capturas/fase-04/pago-rechazado-escritorio-oscuro.jpg) |
| Mis pedidos | [captura](../capturas/fase-04/mis-pedidos-escritorio-oscuro.jpg) |
| Detalle del pedido con seguimiento y factura | [oscuro](../capturas/fase-04/detalle-pedido-escritorio-oscuro.jpg) · [móvil](../capturas/fase-04/detalle-pedido-movil-claro.jpg) |

## 5. Pendientes y riesgos

- La integración con el **Wompi sandbox real** está implementada y probada con firmas, pero no se
  ejecutó contra los servidores de Wompi: hacen falta llaves de sandbox de una cuenta de comercio
  (variables `WOMPI_*`). Se valida en la Fase 9 (despliegue).
- Reembolsos y devoluciones (RMA) llegan en la Fase 6; el pago aprobado tras el vencimiento queda
  registrado para reembolso manual.
- El POS (venta en tienda sin cuenta) llega con el panel en la Fase 5.
