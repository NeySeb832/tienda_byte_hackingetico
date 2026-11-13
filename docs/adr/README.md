# Registro de decisiones de arquitectura (ADR)

Cada ADR documenta una decisión con varias opciones razonables: por qué se eligió una y qué
consecuencias trae. Son cortos a propósito. Si una decisión cambia, se crea un ADR nuevo que la
*reemplaza* y el anterior se marca como "Reemplazada por ADR-XXXX".

| ADR | Título | Estado |
|-----|--------|--------|
| [0001](0001-monolito-modular-con-servicios.md) | Monolito modular con capa de servicios | Aceptada |
| [0002](0002-django-52-lts-y-django-csp.md) | Django 5.2 LTS y CSP con django-csp | Aceptada |
| [0003](0003-permisos-de-objeto-propios.md) | Permisos a nivel de objeto con servicio propio | Aceptada |
| [0004](0004-dinero-decimal-e-iva-incluido.md) | Dinero en Decimal con IVA incluido | Aceptada |
| [0005](0005-dependencias-uv-hashes-cuarentena.md) | Dependencias con uv, hashes y cuarentena de 7 días | Aceptada |
| [0006](0006-frontend-sin-node-alpine-csp.md) | Frontend sin Node: Tailwind standalone, HTMX y Alpine CSP | Aceptada |
| [0007](0007-pasarela-wompi-tras-interfaz.md) | Pasarela Wompi detrás de `PaymentGateway` | Aceptada |
| [0008](0008-checkout-exige-cuenta.md) | El checkout exige cuenta | Aceptada |
| [0009](0009-celery-json-valkey.md) | Celery con serializador JSON sobre Valkey/Redis | Aceptada |
| [0010](0010-bitacora-de-evidencias.md) | Bitácora de evidencias con capturas | Aceptada |
| [0011](0011-identificadores-publicos-y-usuario-email.md) | Identificadores públicos UUID y usuario por email | Aceptada |
| [0012](0012-autenticacion-allauth-axes-turnstile.md) | Autenticación con allauth + MFA, axes, Turnstile y HIBP | Aceptada |

Plantilla: [`template.md`](template.md).
