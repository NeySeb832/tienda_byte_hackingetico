# ADR-0007: Pasarela Wompi detrás de `PaymentGateway`

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
Los pagos deben funcionar en modo sandbox con una pasarela colombiana. Los tests y el desarrollo no
pueden depender de un servicio externo.

## Decisión
- Una interfaz `PaymentGateway` (crear transacción, consultar estado, verificar webhook, reembolsar) con
  dos implementaciones:
  - `WompiGateway`: sandbox, con `httpx`, timeouts y reintentos.
  - `FakeGateway`: determinista, para desarrollo y tests.
- Los webhooks se verifican por firma y marca de tiempo, y son idempotentes por `event_id`.
- Nunca se guardan datos de tarjeta, solo referencias e IDs de la pasarela.

## Consecuencias
- Se puede cambiar a Mercado Pago implementando la interfaz, sin tocar el checkout.
- Los tests cubren pago rechazado, webhook duplicado y firma inválida sin usar la red.

## Alternativas consideradas
- **Mercado Pago**: tiene SDK oficial, pero Wompi es más directo para Colombia (PSE, Nequi,
  Bancolombia) y su firma de eventos es fácil de verificar.
