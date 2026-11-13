# ADR-0014: Checkout con reserva de stock, máquina de estados y pagos que fallan cerrado

- **Estado:** Aceptada
- **Fecha:** 2026-11-13

## Contexto
El checkout debe evitar la sobreventa con compras simultáneas, no confiar en nada que venga del
navegador o de la redirección de la pasarela y dejar trazabilidad de cada cambio. La
especificación pide Wompi en sandbox, webhooks y factura de prueba.

## Decisión
1. **Reserva de stock al crear el pedido**, no al agregar al carrito: `reserve_for_order` bloquea
   las filas de `StockItem` con `SELECT … FOR UPDATE` en orden de PK y reserva todo o nada.
   La reserva dura `BYTE_STOCK_RESERVATION_TTL_MINUTES` (15); una tarea de Beat vence los pedidos
   sin pago y libera las unidades. Al aprobarse el pago, las unidades salen del inventario y se
   registran en el **kardex** (`StockMovement`, append-only con trigger).
2. **Máquina de estados explícita** (`orders.services.TRANSITIONS`) con línea de tiempo
   append-only (`OrderStatusEvent`, trigger en la BD).
3. **Pagos que fallan cerrado:** el resultado de la pasarela solo se aplica si la firma es válida,
   la referencia existe, el pago no es final y el **monto coincide exactamente** con el total.
   Cualquier otra cosa se rechaza y queda como evento de seguridad. Los eventos son idempotentes
   por `event_id`. La página de retorno consulta la transacción servidor a servidor; nunca usa el
   estado de la URL.
4. **Simulador interno** (`BYTE_PAYMENT_GATEWAY=fake`) con eventos firmados por HMAC, para
   desarrollo, tests y demos sin llaves; `byte.W004` lo advierte en `check --deploy`.
5. **Factura electrónica simulada** en PDF (ReportLab 5.1) con CUFE simulado (SHA-384) y la marca
   "documento de prueba".

## Consecuencias
- Un carrito no bloquea stock: dos clientes pueden tener el último producto en el carrito, pero
  solo uno logra crear el pedido.
- Si un pago llega aprobado después del vencimiento, el pedido no se revive: queda registrado
  para reembolso manual (evento de seguridad `payment_after_expiry`).
- La numeración usa secuencias de PostgreSQL (`orders_order_number_seq`, `orders_invoice_number_seq`).

## Alternativas consideradas
- **Reservar al agregar al carrito:** bloquea inventario con carritos abandonados.
- **Confiar en el `status` de la URL de retorno:** trivial de falsificar.
- **WeasyPrint para la factura:** requiere librerías del sistema (Pango, Cairo) en la imagen.
