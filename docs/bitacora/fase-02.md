# Bitácora — Fase 2: Usuarios y seguridad base

- **Fecha:** 2026-11-12
- **Rama:** `fase/02-usuarios-seguridad` (sale de `fase/01-fundaciones`)
- **Objetivo:** autenticación robusta (allauth + MFA), protección contra fuerza bruta, roles y
  permisos con mixins que deniegan por defecto, auditoría inmutable, área "Mi cuenta" con Habeas
  Data, panel de administración base y tests de acceso.

## 1. Qué se hizo

| Entregable | Dónde |
|------------|-------|
| Login, registro, verificación de correo, recuperación, MFA TOTP, sesiones (allauth) | `config/settings/base.py`, `templates/allauth/` |
| Bloqueo progresivo por usuario + IP (axes) y página de bloqueo | `apps/accounts/apps.py`, `templates/account/lockout.html` |
| CAPTCHA Turnstile, honeypot, validadores de contraseña (personal ≥ 12, HIBP) | `apps/accounts/captcha.py`, `forms.py`, `validators.py` |
| 8 roles, `setup_roles`, `export_permissions_matrix` | `apps/accounts/roles.py`, [`docs/matriz-permisos.md`](../matriz-permisos.md) |
| Mixins de acceso, MFA obligatorio y cierre por inactividad del personal | `apps/accounts/permissions.py`, `middleware.py` |
| Perfil cifrado, direcciones (anti-IDOR), consentimiento, exportación y eliminación de datos | `apps/accounts/` |
| Política de datos y términos versionados | `apps/cms/` |
| Auditoría encadenada por hash con trigger en PostgreSQL, eventos de seguridad y alertas | `apps/audit/` |
| Panel `/panel/`: resumen, personal y roles, auditoría, eventos de seguridad | `apps/panel/`, `templates/panel/` |
| Geografía DANE (33 departamentos, 51 municipios) y sedes | `apps/core/`, `apps/inventory/` |
| Usuarios demo por rol | `seed_demo_users` |
| Decisión de arquitectura | [ADR-0012](../adr/0012-autenticacion-allauth-axes-turnstile.md) |

## 2. Cómo se hizo

1. **Versiones verificadas** antes de agregar dependencias: django-allauth 65.21.1, django-axes
   9.0.0, django-ratelimit 4.1.0 (compatible con Django 5.2), cryptography 50.0.2 y httpx 0.28.1. La
   cuarentena de 7 días dejó allauth en la 65.21.1, porque la 65.22.0 tenía un día de publicada.
2. **Lectura de las APIs instaladas** (no de memoria):
   - los settings de allauth (`ACCOUNT_LOGIN_METHODS`, `ACCOUNT_SIGNUP_FIELDS`, `MFA_*`);
   - el sistema de *elements* de allauth, que se sobrescribió para darle el estilo de la tienda;
   - `secure_admin_login`;
   - `AXES_LOCKOUT_TIERS`. axes exige instancias de su propio `LockoutTier`, que no se puede
     importar desde los settings, así que los niveles se declaran como tuplas y se convierten en
     `AccountsConfig.ready()`.
3. **Generación por bloques**: settings y apps transversales, la app de cuentas, el panel con las
   plantillas y los tests. Después, `makemigrations` con nombres fijos y migraciones de datos
   escritas a mano (geografía, documentos legales y trigger de auditoría).
4. **Verificación**:
   - la suite completa contra PostgreSQL;
   - ruff, black y mypy (estricto en `core` y `accounts`);
   - capturas autenticadas con Playwright. Las sesiones se crean con el ORM de Django **antes** de
     abrir el navegador, porque el ORM no puede ejecutarse dentro del bucle async de Playwright;
   - el stack de Docker reconstruido con las dependencias nuevas.

### Problemas encontrados y cómo se resolvieron

| Problema | Solución |
|----------|----------|
| Las migraciones de datos hechas a mano dependían de migraciones de esquema aún inexistentes | Se apartaron, se generaron las de esquema con `--name` fijo y se restauraron |
| El middleware de seguridad del personal usaba `messages` antes de `MessageMiddleware` | Se reordenó el `MIDDLEWARE` |
| El widget de Turnstile no encontraba su plantilla (el renderer de formularios no lee `templates/`) | La plantilla se movió a `apps/accounts/templates/` |
| La activación de MFA redirigía a re-autenticación | Es el comportamiento seguro de allauth. El test ahora comprueba que no hay bucle con el middleware |
| La alerta de fuerza bruta no salía en el test | Se envía con `transaction.on_commit`; el test captura esos callbacks |
| Tras el bloqueo, a veces el limitador de allauth respondía antes que axes (200 con error) | El test verifica lo esencial: el usuario **no** queda autenticado |
| **"Sesiones activas" daba 500** (lo detectó la consola del navegador durante las capturas) | Faltaba `django.contrib.humanize`. Se agregó un test que recorre las páginas de seguridad de la cuenta |
| **"Mi cuenta" mostraba la tarjeta vacía** (lo detectó la revisión visual de las capturas) | Los `{% block %}` dentro de un `{% include %}` no se heredan. El layout pasó a una plantilla base y los tests revisan el contenido |
| El ORM de Django no puede ejecutarse dentro de Playwright (`SynchronousOnlyOperation`) | Las cookies de sesión se crean antes de abrir el navegador |
| El widget de Turnstile nunca deja la red "en reposo" | `capturas.py` espera el evento `load` y como máximo 5 s de red en reposo |

## 3. Por qué

- **allauth en lugar de soluciones a medida** (ADR-0012): cubre el registro, la verificación, MFA,
  la re-autenticación y las sesiones con código auditado. La lógica propia se limita a las reglas de Byte.
- **Combinación usuario + IP** en el bloqueo: si se bloqueara solo por IP, una red compartida (como
  una universidad) dejaría sin acceso a usuarios legítimos.
- **El CAPTCHA falla cerrado y HIBP falla abierto**: el CAPTCHA es un control antiabuso (A10:
  ante la duda, rechazar), mientras que HIBP es una verificación complementaria cuya caída no debe
  impedir los registros.
- **Permisos de objeto con querysets** (ADR-0003): un objeto ajeno responde 404 (no 403), así no se
  revela que existe.
- **Bitácora con trigger en la BD**: ni un error de código ni un acceso directo al ORM pueden
  reescribir la historia. La cadena de hashes además permite detectar alteraciones.
- **Cifrado de campo con *blind index***: protege el documento y el celular si se filtra la base de
  datos, y aun así permite buscar por documento.

## 4. Evidencias

Se generan con `uv run python scripts/evidencia.py --fase 2` y
`uv run python scripts/capturas.py --fase 2 --base-url http://127.0.0.1:8001`.

### Calidad y seguridad

El resumen está en [`00-resumen.svg`](../capturas/fase-02/00-resumen.svg).

| # | Verificación | Resultado |
|---|--------------|-----------|
| 01 | Tests (pytest) contra PostgreSQL 17 | ✅ **448 pasan** (antes 323), cobertura **93,01 %** |
| 02–04 | ruff · black · mypy (estricto en `core` y `accounts`) | ✅ |
| 05 | bandit (severidad media o alta) | ✅ 0 hallazgos |
| 06 | pip-audit (`requirements/prod.txt`, con allauth, axes, cryptography y httpx) | ✅ sin vulnerabilidades conocidas |
| 07 | `check --deploy` (incluye los checks propios `byte.E002`, `E003` y `W003`) | ✅ |
| 08 | Cabeceras de seguridad (la CSP ahora incluye Turnstile) | ✅ |
| 12 | Matriz de permisos generada desde el código | ✅ al día |
| 13 | Integridad de la cadena de auditoría (BD de desarrollo) | ✅ cadena íntegra |
| 09 | Integridad de las librerías JS y Tailwind | ✅ |
| 10 | semgrep `p/django` + `p/python` | ✅ 0 hallazgos |
| 11 | Trivy sobre la imagen de producción reconstruida | ✅ 0 HIGH/CRITICAL corregibles |

Tests nuevos de seguridad (marcador `security`) de esta fase:
- matriz de acceso de **8 roles × 4 vistas del panel** (32 casos) y login obligatorio;
- MFA obligatorio para el personal y cierre por inactividad;
- **IDOR** sobre direcciones (UUID ajeno y UUID aleatorio → 404);
- honeypot y CAPTCHA (falla cerrado);
- mensajes de login que no permiten enumerar usuarios;
- **bloqueo por fuerza bruta** con alerta por correo;
- reglas de asignación de roles (propio rol, superadmins, escalamiento) y cierre de sesiones;
- cifrado en reposo verificado con SQL crudo;
- **trigger que impide UPDATE y DELETE** sobre la auditoría y detección de alteraciones en la cadena;
- ráfaga de 403;
- límite de tasa de la exportación de datos.

### Infraestructura

- `docker compose up --build` con las dependencias nuevas: web *healthy* y `/healthz` → 200. El
  worker y beat también arrancan.
- Migraciones aplicadas a PostgreSQL: trigger `audit_auditlog_append_only`, 33 departamentos, 51
  municipios, política de datos y términos v1.0.

### Pantallas (Playwright, sesiones reales de los usuarios demo)

| Pantalla | Captura |
|----------|---------|
| Iniciar sesión (oscuro y claro, escritorio y móvil) | [login](../capturas/fase-02/login-escritorio-oscuro.jpg) |
| Registro con consentimiento y CAPTCHA | [registro](../capturas/fase-02/registro-escritorio-oscuro.jpg) |
| Política de tratamiento de datos v1.0 | [política](../capturas/fase-02/politica-datos-escritorio-oscuro.jpg) |
| Mi cuenta (cliente) | [resumen](../capturas/fase-02/mi-cuenta-escritorio-claro.jpg) |
| Direcciones | [direcciones](../capturas/fase-02/direcciones-escritorio-oscuro.jpg) |
| Privacidad: autorizaciones, descarga y eliminación | [privacidad](../capturas/fase-02/privacidad-escritorio-oscuro.jpg) |
| Sesiones activas | [sesiones](../capturas/fase-02/sesiones-escritorio-oscuro.jpg) |
| Panel: resumen (superadmin) | [panel](../capturas/fase-02/panel-resumen-escritorio-oscuro.jpg) |
| Panel: personal y roles | [personal](../capturas/fase-02/panel-personal-escritorio-oscuro.jpg) |
| Panel: auditoría encadenada | [auditoría](../capturas/fase-02/panel-auditoria-escritorio-oscuro.jpg) |
| Panel: eventos de seguridad | [seguridad](../capturas/fase-02/panel-seguridad-escritorio-oscuro.jpg) |
| Panel de un vendedor (menú reducido) | [vendedor](../capturas/fase-02/panel-vendedor-escritorio-oscuro.jpg) |
| Vendedor intentando entrar a auditoría → 403 | [403](../capturas/fase-02/403-vendedor-en-auditoria-escritorio-oscuro.jpg) |

En la consola del navegador hubo **0 violaciones de CSP**
([reporte](../capturas/fase-02/consola-navegador.txt)). El único mensaje es el 403 esperado.

## 5. Pendientes y riesgos

- **Correo en producción:** las verificaciones y alertas usan la consola en desarrollo. El proveedor
  (django-anymail) se configura en la Fase 9.
- **Turnstile:** en desarrollo se usan las claves públicas de prueba de Cloudflare. En producción, el
  check `byte.W003` obliga a configurar claves reales.
- **Alcance por sede:** el modelo y el selector `stores_for()` existen. Se aplicarán a inventario,
  pedidos y POS a partir de las fases 4 y 5.
- **Sesiones por dispositivo:** se listan y se pueden cerrar desde "Sesiones activas". Las alertas de
  inicio de sesión desde un dispositivo nuevo quedan para la Fase 8.
- **CSP del admin de Django:** el admin es solo del superadmin y no mostró violaciones en las pruebas
  manuales. Se revisará con ZAP en la Fase 8.
