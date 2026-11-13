# ADR-0012: Autenticación con allauth + MFA, axes, Turnstile y HIBP

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
La especificación exige:
- verificación de correo y MFA TOTP con códigos de recuperación, obligatorio para el personal;
- bloqueo progresivo por usuario + IP;
- CAPTCHA tras intentos fallidos y en el registro;
- contraseñas de al menos 12 caracteres para el personal, con verificación contra filtraciones;
- rotación de sesión, listado y cierre de sesiones;
- mensajes de error que no permitan enumerar usuarios.

## Decisión
- **django-allauth 65 (account + mfa + usersessions)** para el registro, la verificación de correo, el login por email, la recuperación de contraseña, TOTP con códigos de recuperación, la re-autenticación y la gestión de sesiones activas. `ACCOUNT_PREVENT_ENUMERATION` evita la enumeración de usuarios.
- **django-axes 9** como primer backend de autenticación, con bloqueo por **combinación usuario + IP** y **niveles progresivos**: 5 fallos → 5 min, 10 → 30 min y 20 → 24 h. Los niveles se declaran como tuplas en los settings y se convierten a `LockoutTier` en `AccountsConfig.ready()`, porque `axes.conf` no se puede importar desde los settings.
- **Cloudflare Turnstile** en el registro y en la recuperación de contraseña, y en el login después de 3 fallos desde la misma IP. La verificación **falla cerrada** (A10): si Cloudflare no responde, se rechaza la solicitud.
- **Have I Been Pwned** con k-anonimato: solo salen del servidor 5 caracteres del hash. Si el servicio no responde, la verificación **falla abierta** y queda registrada, porque bloquear todos los registros ante una caída externa afectaría la disponibilidad y el resto de validadores sigue activo.
- **Honeypot** en el registro y en la recuperación de contraseña.
- **MFA obligatorio para el personal y cierre por inactividad** (15 min) con `StaffSecurityMiddleware`. El admin de Django pasa por el login de allauth (`secure_admin_login`) y es exclusivo del superadmin.
- **Cambio de rol**: se cierran todas las sesiones del usuario afectado. Un rol privilegiado genera un evento de seguridad y una alerta.

## Consecuencias
- Hay protección en capas: el rate limit de allauth, el bloqueo de axes, el CAPTCHA y las alertas por correo al superadmin.
- Los tests usan `force_login`: `AxesStandaloneBackend` exige `request` en `authenticate()`.
- La CSP permite `https://challenges.cloudflare.com` en `script-src` y `frame-src`. El script solo se carga en las páginas con CAPTCHA y siempre con nonce.

## Alternativas consideradas
- **django-two-factor-auth**: duplica lo que ya ofrece allauth y requiere más integración.
- **hCaptcha**: es equivalente, pero Turnstile no rastrea al usuario y la mayoría de las veces no le pide interacción.
- **Bloqueo solo por IP**: castiga a usuarios legítimos detrás de un NAT (por ejemplo, universidades), por eso se combina con el usuario.
