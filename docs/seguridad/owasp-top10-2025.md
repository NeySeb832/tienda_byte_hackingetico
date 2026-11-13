# Matriz OWASP Top 10:2025 — Byte

Cada fila enlaza el control implementado con la evidencia automática que lo verifica.
`tests/security/test_owasp_2025.py` agrupa una prueba por categoría; las demás pruebas citadas
están en `tests/security/` y en las apps.

| Categoría | Controles en Byte | Evidencia |
|-----------|-------------------|-----------|
| **A01 Control de acceso roto** | Denegación por defecto (`RoleRequiredMixin`, `StaffRequiredMixin`), permisos por vista y por acción, alcance por sede, PK internas nunca expuestas (UUID públicos), objetos ajenos → 404, CSRF en toda escritura, redirecciones validadas | `test_access_control.py` (matriz rol × vista), `test_operations.py` (77 casos), IDOR en direcciones, pedidos, facturas, tickets y traslados |
| **A02 Configuración de seguridad incorrecta** | Settings por entorno, `check --deploy` sin advertencias, checks propios `byte.E001–E004`/`W001–W004`, HSTS, cookies `__Host-` seguras, admin oculto y solo superadmin, DEBUG falso en prod | `test_settings.py`, evidencia `07-check-deploy`, ZAP baseline |
| **A03 Fallas en la cadena de suministro** | `uv.lock` con hashes y cuarentena de 7 días, `requirements` con `--require-hashes`, imágenes y Actions fijadas por digest/SHA, JS servido localmente con sha512, Tailwind con sha256, pip-audit, Trivy, **SBOM CycloneDX** | evidencias `06-pip-audit`, `09-vendor`, `11-trivy`, `14-sbom` |
| **A04 Fallas criptográficas** | Argon2 para contraseñas, documento y celular cifrados (MultiFernet con rotación), blind index HMAC, HTTPS forzado, sin datos de tarjeta (pasarela) | `test_crypto.py`, `test_settings.py::argon2`, cifrado verificado con SQL crudo |
| **A05 Inyección** | ORM con parámetros, búsqueda con lista blanca de orden y filtros tolerantes, SQL analítico constante (DuckDB), autoescapado y CSP con nonce, CSV sin fórmulas | `test_catalog_security.py` (XSS), `test_selectors.py` (entrada hostil), `test_operations.py::csv` |
| **A06 Diseño inseguro** | Separación de funciones en ajustes, compras, cupones, devoluciones y reembolsos (servicio + `CHECK`), reserva de stock todo o nada, máquinas de estado, límites de cantidad, modelo STRIDE | `docs/seguridad/stride.md`, tests de SoD en inventario, compras, cupones y devoluciones |
| **A07 Fallas de autenticación** | allauth con verificación de correo, MFA obligatorio para el personal, bloqueo progresivo (axes), Turnstile, HIBP, cierre por inactividad, mensajes que no enumeran usuarios | `test_auth_flows.py`, `test_access_control.py` (MFA, inactividad) |
| **A08 Fallas de integridad de software y datos** | Webhooks con firma y monto exacto (fallan cerrado), idempotencia por `event_id`, registros append-only con trigger (auditoría encadenada por hash, precios, kardex, puntos, saldo, líneas de tiempo), Celery solo JSON | `test_gateways.py`, `verify_audit_chain`, tests de triggers |
| **A09 Fallas de registro y alertas** | Auditoría de toda operación relevante, eventos de seguridad con alerta por correo, logs JSON con `request_id` y enmascarado de datos sensibles, consulta de clientes auditada | `test_audit.py`, `test_logging.py`, evidencia `13-cadena-auditoria` |
| **A10 Manejo incorrecto de condiciones excepcionales** | Errores genéricos con ID de correlación, falla cerrada en permisos, pagos, CAPTCHA y antifraude, transacciones atómicas, límites de tasa | `test_errors.py`, `test_owasp_2025.py::test_a10_*` |
