# Bitácora · Fase 6 — Valor agregado

- **Rama:** `fase/06-valor-agregado`
- **Fecha:** 2026-11-13
- **Estado:** ✅ en revisión

## 1. Qué se hizo

- Retomas con cotización en línea y oferta final en tienda.
- Byte Puntos y saldo a favor en libros contables append-only, con pago con saldo en el POS.
- Servicio técnico con órdenes, código de seguimiento, cotización aprobada por el cliente y garantía.
- Alertas de disponibilidad y de baja de precio.
- Devoluciones (retracto, comercial y garantía) con reembolso aprobado por otra persona.
- Preventas con fecha de lanzamiento.

## 2. Cómo se hizo

- **Libros contables:** `LoyaltyEntry` y `CreditEntry` heredan de un modelo abstracto que guarda
  el delta y el saldo resultante. `promotions.services._append` toma un bloqueo consultivo de
  PostgreSQL por usuario (clave estable con `zlib.crc32`, porque `hash()` cambia entre procesos),
  lee el último saldo y agrega la fila. Un trigger impide `UPDATE` y `DELETE`.
- **Integración:** al aprobarse un pago (web) o al vender en el POS a un cliente identificado por
  correo, se otorgan los puntos una sola vez (índice único parcial por pedido). El POS acepta
  "saldo a favor" como medio de pago y lo descuenta del libro.
- **Retomas:** el precio de referencia es el más bajo de la consola en condición "Usado" (o el
  más bajo si no hay usada), por un factor de estado (55/45/30 %), −5 % sin caja, −10 % sin
  control, redondeado hacia abajo a $ 10.000.
- **Servicio técnico:** máquina de estados del personal (`STAFF_TRANSITIONS`) y del cliente
  (`answer_quote`), línea de tiempo append-only y correo en "cotizado" y "listo". El código usa
  un alfabeto sin 0/O/1/I para dictarlo por teléfono.
- **Alertas:** `set_stock`/`move_stock` (al aumentar) y el motor de precios (al bajar) encolan
  `process_alerts` con `transaction.on_commit`; la tarea marca la alerta antes de enviar.
- **Devoluciones:** plazos con días hábiles (sin fines de semana), cantidades limitadas a lo no
  devuelto, reingreso al kardex con motivo "Devolución" y reembolso proporcional al descuento
  del pedido.

### Problemas encontrados y cómo se resolvieron

| Problema | Solución |
|----------|----------|
| `FOR UPDATE cannot be applied to the nullable side of an outer join` al aprobar reembolsos | `select_for_update(of=("self",))` |
| La clave del bloqueo consultivo usaba `hash()`, distinto en cada proceso | `zlib.crc32` del nombre de la tabla |
| El inicio mostraba los 7 servicios técnicos al pasar a la BD | El inicio muestra los 4 principales |
| Las vistas nuevas quedaron con 47–51 % de cobertura | Tests de flujo por las páginas: 92–95 % |

**Fase 5 (cierre):** la primera corrida de evidencias de la Fase 5 dio 2 fallos (un `redirect`
armado con `request.path`, señalado por semgrep, y un import en un test, señalado por mypy). Se
corrigieron antes del commit de la fase y se repitieron ruff, black, mypy, semgrep y pytest en una
copia de trabajo (`git worktree`) de ese commit: todo en OK, semgrep con 0 hallazgos.

## 3. Por qué

- **Saldo como libro y no como número:** cada peso de saldo tiene origen, autor y fecha; no hay
  forma de "editar" un saldo sin dejar rastro (OWASP A04/A08).
- **Separación de funciones en reembolsos:** quien recibe el producto no puede aprobar la
  devolución del dinero (ADR-0016).
- **Seguimiento público con código y correo, con límite de tasa:** el código por sí solo no da
  acceso, y no se pueden probar códigos en masa.
- **Alertas después del commit:** nunca se avisa de un cambio que luego se revierte.

## 4. Evidencias

El resumen está en [`00-resumen.svg`](../capturas/fase-06/00-resumen.svg).

RESULTADOS_EVIDENCIAS

### Pantallas (Playwright)

Consola del navegador: **0 mensajes y 0 violaciones de CSP**
([`consola-navegador.txt`](../capturas/fase-06/consola-navegador.txt)).

| Pantalla | Captura |
|----------|---------|
| Inicio con servicios desde la BD y botón de retoma | [captura](../capturas/fase-06/inicio-servicios-y-retoma-escritorio-oscuro.jpg) |
| Mis retomas con oferta final | [claro](../capturas/fase-06/cuenta-retomas-escritorio-claro.jpg) · [móvil](../capturas/fase-06/cuenta-retomas-movil-oscuro.jpg) |
| Puntos y saldo | [captura](../capturas/fase-06/cuenta-puntos-y-saldo-escritorio-oscuro.jpg) |
| Servicio técnico: cotización por aprobar | [captura](../capturas/fase-06/cuenta-servicio-tecnico-escritorio-oscuro.jpg) |
| Alertas y ficha con botones de alerta | [alertas](../capturas/fase-06/cuenta-alertas-escritorio-oscuro.jpg) · [ficha](../capturas/fase-06/ficha-con-alertas-escritorio-oscuro.jpg) |
| Solicitud de devolución con plazos | [oscuro](../capturas/fase-06/cuenta-devolucion-escritorio-oscuro.jpg) · [móvil](../capturas/fase-06/cuenta-devolucion-movil-claro.jpg) |
| Seguimiento público | [captura](../capturas/fase-06/seguimiento-publico-escritorio-oscuro.jpg) |
| Panel: retomas, servicio técnico y orden | [retomas](../capturas/fase-06/panel-retomas-escritorio-oscuro.jpg) · [lista](../capturas/fase-06/panel-servicio-tecnico-escritorio-oscuro.jpg) · [orden](../capturas/fase-06/panel-orden-de-servicio-escritorio-oscuro.jpg) |
| Panel: devoluciones (el gerente aprueba lo que recibió el vendedor) | [captura](../capturas/fase-06/panel-devoluciones-gerente-escritorio-oscuro.jpg) |

## 5. Pendientes y riesgos

- Los festivos no se descuentan del plazo de retracto (a favor del cliente).
- El saldo a favor se usa en el POS; usarlo en el checkout web queda pendiente.
- Las reseñas de compradores verificados (app `reviews`) no estaban en el alcance de esta fase.
