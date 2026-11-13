# ADR-0008: El checkout exige cuenta

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
Los invitados pueden navegar y armar su carrito. Pagar, en cambio, implica consentimiento de
tratamiento de datos (Ley 1581 de 2012), seguimiento del pedido, devoluciones y reseñas de
compradores verificados.

## Decisión
- El carrito de invitado se guarda en la sesión y **se fusiona** al iniciar sesión.
- Para pagar se exige una cuenta con el correo verificado.
- El POS sí puede vender sin cliente: el pedido queda asociado a la sede y al vendedor.

## Consecuencias
- Cada pedido web tiene dueño, lo que simplifica los permisos (ADR-0003) y la trazabilidad del
  consentimiento.
- Hay más fricción en el primer pedido; se mitiga permitiendo crear la cuenta dentro del checkout.

## Alternativas consideradas
- **Checkout de invitado con enlace mágico**: amplía la superficie de ataque (tokens de acceso a
  pedidos) y complica el derecho de supresión.
