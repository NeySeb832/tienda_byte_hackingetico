# Manual del personal (panel `/panel/`)

El panel exige verificación en dos pasos y se cierra tras 15 minutos sin actividad. Cada persona
ve solo las sedes asignadas y solo los menús de su rol ([matriz](../matriz-permisos.md)).

## Vendedor / Cajero
- **Punto de venta:** abre el turno con la base de caja. En "Nueva venta" escribe una línea por
  producto (`SKU x cantidad`), elige efectivo (indica lo recibido: se calcula el cambio), datáfono
  o saldo a favor (requiere el correo del cliente). Al cerrar, cuenta el efectivo: el sistema
  muestra la diferencia con lo esperado.
- **Pedidos:** prepara, marca "listo para recoger" y "entregado".
- **Devoluciones:** recibe el producto (con o sin reingreso al stock). La aprobación del
  reembolso la hace otra persona.
- **Retomas y servicio técnico:** recibe equipos y evalúa consolas.

## Bodeguero
- **Inventario:** existencias por sede (físico, reservado, disponible) y kardex por producto.
- **Ajustes:** solicita la corrección tras un conteo (quedan pendientes de aprobación).
- **Traslados:** solicita; la sede de origen despacha y la de destino recibe.
- **Compras:** registra recepciones parciales de órdenes aprobadas.

## Técnico de soporte
Recibe el equipo, diagnostica, cotiza (el cliente aprueba en su cuenta), repara y entrega con
90 días de garantía. Evalúa retomas con la oferta final.

## Gerente de tienda
Todo lo anterior más: **aprobar** ajustes, órdenes de compra, cupones de más del 15 % y reembolsos
(nunca los propios), cambiar o programar **precios**, ver **clientes** (cada consulta queda en la
auditoría), **reportes** con CSV y **BI**.

## Analista de datos
Reportes operativos y **Inteligencia de negocio**: ventas mensuales con pronóstico, categorías,
sedes, canales, segmentos RFM y productos más vendidos.

## Administrador y superadmin
Gestión de personal y roles (nadie cambia su propio rol), auditoría y, solo el superadmin, eventos
de seguridad y el admin de Django en su ruta oculta.
