# ADR-0001: Monolito modular con capa de servicios

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
Byte abarca catálogo, inventario multi-sede, pedidos, pagos, POS, postventa y analítica. Lo
desarrolla un equipo pequeño y se despliega en una PaaS (Render). La lógica de negocio (precios,
stock, estados de pedido, aprobaciones) es crítica y debe poder probarse sin pasar por HTTP.

## Decisión
Un solo proyecto Django dividido en apps por dominio (`apps/<dominio>`). Cada app separa:
- `services.py`: casos de uso de escritura, transaccionales.
- `selectors.py`: lecturas optimizadas y filtradas por permisos.
- `views.py`, `forms.py` y los serializers: solo HTTP.
- `permissions.py`: reglas de acceso.

Dos apps transversales completan la estructura:
- `core`: modelos base, dinero, middleware, errores y salud.
- `panel`: carcasa de `/panel/`.

## Consecuencias
- Las reglas de negocio se prueban como funciones: tests rápidos y cobertura medible en `services.py`.
- Un despliegue, una base de datos y transacciones ACID entre dominios (por ejemplo, pedido y stock en
  la misma transacción).
- Exige disciplina: una app usa los servicios y selectors de otra en lugar de tocar sus modelos desde
  las vistas. `tests/test_structure.py` vigila la estructura mínima.

## Alternativas consideradas
- **Microservicios**: requieren orquestación y transacciones distribuidas, y suman superficie de
  ataque. Desproporcionado para el tamaño del proyecto.
- **Lógica en vistas o "modelos gordos"**: más rápido al inicio, pero difícil de probar y auditar.
