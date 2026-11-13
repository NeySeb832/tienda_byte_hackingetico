# Bitácora · Fase 8 — Endurecimiento de seguridad

- **Rama:** `fase/08-seguridad` · **Fecha:** 2026-11-13 · **Estado:** ✅ en revisión

## Qué
- [Matriz OWASP Top 10:2025](../seguridad/owasp-top10-2025.md): control → evidencia por categoría.
- [Modelo STRIDE](../seguridad/stride.md) con riesgo residual.
- `tests/security/test_owasp_2025.py`: una garantía transversal por categoría (panel cerrado a
  anónimos y clientes, sin PK en URLs, dependencias con hashes y Actions por SHA, Argon2 y
  secretos por entorno, entrada hostil, SoD con `CHECK` en la BD, MFA obligatorio, triggers
  append-only en 7 tablas, lectura auditada, errores genéricos con ID de correlación).
- **SBOM CycloneDX** de producción ([`sbom.cdx.json`](../seguridad/sbom.cdx.json)) y **OWASP ZAP
  baseline** ([informe](../seguridad/zap-baseline.html)) integrados en `scripts/evidencia.py`
  (`14-sbom`, `15-zap` con `BYTE_ZAP_TARGET`).

## Resultado de ZAP 2.17.0 (baseline, pasivo + spider)
**0 fallos, 55 reglas superadas, 13 advertencias**, todas revisadas:

| Advertencia | Análisis |
|-------------|----------|
| CSP, X-Content-Type-Options, Permissions-Policy, COEP ausentes | Solo en archivos estáticos servidos por `runserver` de desarrollo (no pasan por los middlewares). En producción WhiteNoise los sirve con `nosniff`; las páginas sí llevan CSP con nonce y Permissions-Policy |
| Server leaks version | Cabecera de `runserver`; en producción responde gunicorn detrás del proxy de Render |
| Cross-Domain JavaScript / SRI | Turnstile de Cloudflare (no ofrece hashes estables); el resto de JS es local con integridad verificada |
| User Controllable HTML Attribute | Parámetros de filtros reflejados en `value=` con autoescapado (falso positivo; cubierto por `test_a05`) |
| Session/Authentication identified, Storable content, Suspicious comments, Dangerous JS | Informativas: formularios de login, páginas públicas cacheables y código minificado de terceros |

## Evidencias
| Verificación | Resultado |
|--------------|-----------|
| Tests (BD recién creada) | ✅ **724 pasan**, cobertura **93 %** |
| ruff · black · mypy · bandit · pip-audit · check --deploy · cabeceras · vendor · matriz · auditoría | ✅ |
| SBOM CycloneDX | ✅ `docs/seguridad/sbom.cdx.json` |
| OWASP ZAP baseline | ✅ 0 fallos (13 advertencias analizadas arriba) |
| semgrep | ✅ **0 hallazgos** en 152 reglas y 414 archivos |
| Trivy | ✅ 0 HIGH/CRITICAL corregibles |

## Pendientes
ZAP activo (ataque) solo contra un entorno de staging, nunca contra producción.
