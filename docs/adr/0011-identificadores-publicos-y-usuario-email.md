# ADR-0011: Identificadores públicos UUID y usuario por email

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
Los IDs autoincrementales en las URLs permiten enumerar recursos (IDOR, A01:2025) y revelan el volumen
del negocio. Django recomienda definir un modelo de usuario propio **antes** de la primera migración.

## Decisión
- Todo modelo expuesto hereda de `PublicIdModel`: `public_id = UUIDField(default=uuid4, unique=True)`.
  Las URLs y la API usan `public_id` o `slug`, y la PK `bigint` queda interna.
- `accounts.User` es un usuario propio con el **email como identificador**, sin `username`. El email
  se guarda en minúsculas, y un `CHECK` en la BD impide guardarlo con mayúsculas aunque se salte el
  ORM o el formulario.

## Consecuencias
- Los recursos no se pueden enumerar; los tests de IDOR prueban con UUIDs ajenos.
- Las relaciones internas siguen usando `bigint`, que es eficiente para joins e índices.

## Alternativas consideradas
- **UUID como PK**: fragmenta los índices y empeora el rendimiento con 500.000 pedidos o más.
- **Hashids**: es solo una ofuscación reversible, no un identificador opaco.
