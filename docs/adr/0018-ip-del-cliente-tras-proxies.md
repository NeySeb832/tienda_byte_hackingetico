# ADR-0018: IP del cliente tras proxies (Cloudflare y Render)

- **Estado:** Aceptada
- **Fecha:** 2026-11-13

## Contexto
La prueba de penetración (hallazgo PT-01) mostró que el bloqueo por fuerza bruta no funcionaba en
producción. Causa raíz: todos los controles por IP (django-axes, django-ratelimit, los límites de
allauth, la bitácora de auditoría y el CAPTCHA adaptativo del inicio de sesión) usaban
`REMOTE_ADDR`. En Render esa dirección es privada (`10.x`) y pertenece al balanceador, que comparten
muchos visitantes y que cambia entre peticiones. Los ajustes `AXES_IPWARE_*` no tenían efecto porque
django-ipware no está instalado.

En Render, la cabecera `X-Forwarded-For` llega como `cliente, borde de Cloudflare`, pero Render solo
agrega entradas: lo que envíe el cliente queda a la izquierda, así que la primera entrada se puede
falsificar. Cloudflare, que está delante de todos los servicios `*.onrender.com`, escribe la IP real
en `CF-Connecting-IP` y sobrescribe cualquier valor que mande el cliente.

## Decisión
Una sola función, `apps.core.net.client_ip`, resuelve la IP para todos los controles
(`AXES_CLIENT_IP_CALLABLE`, `RATELIMIT_IP_META_KEY` y `AccountAdapter.get_client_ip`). Se configura
por entorno:

1. `BYTE_CLIENT_IP_HEADER`: cabecera de un borde que el cliente no puede saltarse. En Render,
   `HTTP_CF_CONNECTING_IP`.
2. `BYTE_TRUSTED_PROXY_COUNT`: N saltos de confianza contados desde la derecha de `X-Forwarded-For`,
   para despliegues sin Cloudflare.
3. `REMOTE_ADDR` como último recurso (desarrollo).

Solo se aceptan direcciones IP válidas. El chequeo `byte.W005` de `check --deploy` avisa si
producción queda resolviendo desde `REMOTE_ADDR`.

## Consecuencias
- El bloqueo por usuario + IP, los límites por IP y la auditoría vuelven a identificar al cliente.
- Si el servicio dejara de estar detrás de Cloudflare, la cabecera faltaría y se usaría
  `REMOTE_ADDR` (falla segura hacia el comportamiento anterior, no hacia una IP falsificable).
- Hay que repetir la prueba de fuerza bruta tras cada cambio de infraestructura.

## Alternativas consideradas
- **Instalar django-ipware:** cubre solo axes; django-ratelimit y allauth calculan la IP por su cuenta.
- **Primera entrada de `X-Forwarded-For`:** falsificable en Render.
- **Bloqueo solo por IP:** castiga a redes compartidas (universidades); se mantiene usuario + IP,
  más el límite de allauth por IP y el CAPTCHA en todo inicio de sesión en producción.
