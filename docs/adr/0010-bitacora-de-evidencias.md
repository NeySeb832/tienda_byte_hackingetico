# ADR-0010: Bitácora de evidencias con capturas

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
El proyecto se sustenta académicamente. El usuario pidió capturas de cada avance y una descripción de
*qué* se hizo, *cómo* y *por qué*.

## Decisión
- Una bitácora por fase en `docs/bitacora/fase-NN.md`, con las secciones Qué se hizo · Cómo · Por qué
  (con enlaces a los ADR) · Evidencias · Pendientes y riesgos.
- `scripts/capturas.py` usa Playwright para capturar las pantallas de la fase en escritorio y móvil,
  en modo claro y oscuro, y las guarda en `docs/capturas/fase-NN/*.jpg`.
- `scripts/evidencia.py` ejecuta los tests, los linters y el análisis de seguridad, y guarda cada
  salida como SVG (con `rich`) y como TXT en la misma carpeta.
- Al cerrar la fase, las capturas también se muestran en el chat.

## Consecuencias
- La evidencia es reproducible: cualquier persona la regenera con un comando.
- El repositorio crece con imágenes. Se mitiga con JPEG de calidad 85, SVG (que es texto) y capturando
  solo las vistas representativas.

## Alternativas consideradas
- **Capturas manuales**: no se pueden reproducir, son lentas y quedan desactualizadas.
