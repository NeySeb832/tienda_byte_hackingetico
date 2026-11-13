# Guion de sustentación (20 minutos)

1. **Problema y alcance (2 min).** Cadena de videojuegos en Colombia: tienda en línea, POS, panel
   y BI. La seguridad es un requisito de primer nivel (OWASP Top 10:2025).
2. **Arquitectura (3 min).** Monolito modular con servicios y selectores, PostgreSQL como fuente
   de verdad de las reglas (`CHECK`, triggers), Celery con JSON y DuckDB para BI. Mostrar ADR-0001,
   0014 y 0017.
3. **Demo de cliente (4 min).** Búsqueda con error de tipeo, configurador, carrito de invitado,
   login con fusión del carrito, checkout, simulador de pago, factura PDF y puntos ganados
   (`scripts/e2e.py` como respaldo si falla la red).
4. **Demo del panel (4 min).**
   - Bodega solicita un ajuste y no puede aprobarlo; el gerente sí.
   - Venta en el POS con cambio, cierre de caja con diferencia y kardex.
   - Devolución: el vendedor recibe y el gerente aprueba el reembolso.
5. **Seguridad en vivo (4 min).**
   - IDOR: el pedido de otro cliente responde 404.
   - Webhook con firma falsa → 400 y evento de seguridad.
   - Monto alterado → el pago queda en error, no aprobado.
   - `UPDATE` sobre el historial de precios → rechazado por el trigger.
   - `verify_audit_chain`.
   - ZAP: 0 fallos; semgrep: 0 hallazgos.
6. **BI (2 min).** Medallón, modelo estrella, RFM y pronóstico; sin datos personales en el lago.
7. **Cierre (1 min).** Errores encontrados y corregidos en el camino, documentados con
   honestidad en la bitácora (semgrep de la Fase 2, redirección de la Fase 5, créditos fuera del
   repositorio). Pendientes: despliegue con llaves reales del sandbox y festivos en el retracto.

**Preguntas probables:**
- ¿Por qué no Elasticsearch o Spark? Respuestas en ADR-0013 y ADR-0017.
- ¿Cómo se evita la sobreventa? `SELECT FOR UPDATE` en orden de PK, con reserva todo o nada.
- ¿Qué pasa si Wompi no confirma? El pedido vence, el stock se libera y un pago tardío queda
  para reembolso.
