# ADR-0015: Panel operativo con separación de funciones y alcance por sede

- **Estado:** Aceptada
- **Fecha:** 2026-11-13

## Contexto
El panel concentra operaciones sensibles: cambiar stock, comprar mercancía, vender en mostrador,
cambiar precios y crear descuentos. Un solo usuario no debería poder crear y aprobar su propia
operación, y el personal de una sede no debería ver ni tocar la información de otra.

## Decisión
1. **Separación de funciones en servicio y base de datos:** ajustes de inventario, órdenes de
   compra y cupones con más de 15 % de descuento los aprueba una persona distinta de quien los crea.
   Además de la validación en el servicio, hay `CHECK` en PostgreSQL
   (`decided_by <> requested_by`, `approved_by <> created_by`).
2. **Alcance por sede:** todas las consultas del panel parten de `stores_for(user)`. Un objeto de
   otra sede responde 404, no 403, para no revelar que existe. En los traslados, solo la sede de
   origen despacha y solo la de destino recibe.
3. **Un único camino para el stock:** las ventas en mostrador (POS) son pedidos con canal `pos` que
   pasan por la misma reserva y el mismo consumo que la tienda web. Las compras, los traslados y los
   ajustes escriben en el kardex con `move_stock` o `set_stock`.
4. **Permisos explícitos por vista** (`required_permissions`) y por acción: ver no implica poder
   aprobar. La matriz de roles vive en `apps/accounts/roles.py` y se publica en
   `docs/matriz-permisos.md`.
5. **Trazabilidad:** abrir la ficha de un cliente queda en la auditoría (Ley 1581), igual que
   exportar reportes. Los CSV neutralizan fórmulas (`=`, `+`, `-`, `@`) para evitar la inyección
   de fórmulas en hojas de cálculo.

## Consecuencias
- Una sede con una sola persona no puede aprobar sus propios ajustes: tiene que intervenir el
  gerente o un administrador. Es una decisión de control interno, no un error.
- El POS no maneja todavía devoluciones en mostrador (Fase 6).

## Alternativas consideradas
- **Permisos de objeto con django-guardian:** más flexible, pero innecesario; el alcance por
  sede ya cubre el caso (ADR-0003).
- **Ajustes sin aprobación por debajo de un umbral:** más ágil, pero abre la puerta a robos
  hormiga; se deja para cuando el negocio lo pida.
