# ADR-0002: Django 5.2 LTS y CSP con django-csp

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
Al 12-nov-2026 la última versión de Django es la 6.1.3, que incluye CSP nativa desde la 6.0. La LTS
vigente es la **5.2** (5.2.19), con soporte de seguridad hasta abril de 2028. La próxima LTS, la 6.2,
se espera para abril de 2027. La especificación pide la LTS vigente.

## Decisión
Django **5.2 LTS** (`>=5.2.19,<5.3`) con **django-csp 4.x** para una CSP estricta basada en nonces.

## Consecuencias
- Soporte largo y estable durante todo el proyecto y su sustentación.
- La CSP se configura con `CONTENT_SECURITY_POLICY` de django-csp y el nonce se obtiene con
  `request.csp_nonce`.
- Al migrar a la 6.2 LTS se podrá reemplazar django-csp por la CSP nativa (deuda técnica documentada).
- django-stubs se fija en la serie 5.2 para que los tipos coincidan.

## Alternativas consideradas
- **Django 6.1**: tiene CSP nativa, pero no es LTS (su soporte termina antes) y contradice la
  especificación.
