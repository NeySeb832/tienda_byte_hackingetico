# ADR-0016: Puntos y saldo en libros append-only; devoluciones con reembolso aprobado por otra persona

- **Estado:** Aceptada
- **Fecha:** 2026-11-13

## Contexto
Retomas, puntos de fidelidad, saldo a favor y reembolsos mueven valor económico. Un saldo
guardado como un número editable se puede alterar sin dejar rastro, y un reembolso aprobado por
quien lo registra abre la puerta al fraude interno.

## Decisión
1. **Libros contables append-only** (`LoyaltyEntry`, `CreditEntry`): cada movimiento guarda el
   delta y el saldo resultante; el saldo vigente es el de la última fila. Se agregan bajo un
   bloqueo consultivo de PostgreSQL por usuario (`pg_advisory_xact_lock`), con
   `CHECK (balance >= 0)`, sin `UPDATE` ni `DELETE` (ORM y trigger). Los puntos de un pedido se
   otorgan una sola vez (índice único parcial).
2. **Reglas de fidelidad:** 1 punto por cada $ 1.000 pagados; 1.000 puntos se canjean por
   $ 10.000 de saldo. Un reembolso descuenta la parte proporcional de los puntos ganados.
3. **Retomas:** cotización en línea con el precio de referencia de la consola usada y un factor
   por estado; la oferta final la hace en tienda una persona distinta del cliente. El pago en
   saldo tiene un 10 % adicional.
4. **Devoluciones (RMA):** retracto de 5 días hábiles (Ley 1480, art. 47), devolución comercial
   de 30 días y garantía. Quien recibe el producto no puede aprobar el reembolso (servicio y
   `CHECK`); el `Refund` guarda quién lo pidió y quién lo aprobó (`CHECK` también).
5. **Alertas de stock y precio:** se procesan después del commit con Celery y se marcan como
   enviadas antes de enviar el correo (como máximo una vez).

## Consecuencias
- Las correcciones de saldo son movimientos nuevos, nunca ediciones.
- Los festivos nacionales no se descuentan en el plazo de retracto (solo fines de semana):
  limitación documentada, a favor del cliente.
- Los reembolsos a Wompi quedan como "pendiente en la pasarela" (en el sandbox se ejecutan desde
  su panel); los del simulador, efectivo y datáfono quedan aprobados.

## Alternativas consideradas
- **Campo `balance` en el perfil:** simple, pero sin historial ni protección.
- **Plazo de retracto con calendario de festivos:** requiere mantener festivos por año; se
  deja para cuando el negocio lo pida.
