# Modelo de amenazas STRIDE — Byte

Límites de confianza: navegador ↔ Django (Internet), Django ↔ Wompi (webhook), Django ↔
PostgreSQL/Valkey (red privada), Celery ↔ correo, panel (personal) ↔ tienda (clientes).

| Amenaza | Escenario | Mitigación | Riesgo residual |
|---------|-----------|------------|-----------------|
| **S**uplantación | Robo de credenciales del personal | MFA obligatorio, bloqueo progresivo, HIBP, cierre por inactividad, sesiones visibles y revocables | Bajo |
| **S**uplantación | Webhook falso de la pasarela | Firma SHA-256 con secreto de eventos, referencia y monto exactos, evento de seguridad | Bajo |
| **T**ampering | Cambiar precios o saldos en la BD | Historial de precios, kardex, puntos y saldo append-only con trigger; auditoría encadenada por hash | Bajo (un DBA con superusuario podría desactivar triggers: se detecta con `verify_audit_chain`) |
| **T**ampering | Alterar el monto en el navegador | Totales siempre calculados en el servidor; la URL de retorno no decide el estado | Bajo |
| **R**epudio | "Yo no aprobé ese reembolso" | Auditoría con actor, IP y `request_id`; SoD con `CHECK` | Bajo |
| **I**nformación | IDOR entre clientes o sedes | UUID públicos, filtros por dueño/sede, 404 | Bajo |
| **I**nformación | Datos personales en el lago de datos | Cliente como HMAC, sin correos ni teléfonos | Bajo |
| **I**nformación | Fuga en errores | Páginas genéricas con ID de correlación; detalle solo en logs con enmascarado | Bajo |
| **D**enegación de servicio | Fuerza bruta en login, cupones, autocompletado, webhook | axes, Turnstile, `django-ratelimit`, límite de 64 KB en webhooks | Medio (sin WAF propio; Render/Cloudflare delante) |
| **D**enegación de servicio | Acaparar stock con pedidos sin pagar | Reserva de 15 min que vence por Beat; máximo por pedido | Bajo |
| **E**levación de privilegios | Un gerente se asigna superadmin | Solo un superadmin gestiona superadmins; nadie cambia su propio rol; alerta de ascenso | Bajo |
| **E**levación de privilegios | XSS para robar la sesión de un admin | CSP estricta con nonce, autoescapado, cookies `HttpOnly` y `__Host-` | Bajo |
