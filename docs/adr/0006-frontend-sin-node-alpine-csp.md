# ADR-0006: Frontend sin Node: Tailwind standalone, HTMX y Alpine CSP

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
La interfaz se arma con plantillas Django, HTMX, Alpine.js y Tailwind CSS. La CSP debe ser estricta,
sin `unsafe-inline` ni `unsafe-eval`. El equipo de desarrollo no tiene Node, y sumarlo amplía la cadena
de suministro (`node_modules`).

## Decisión
- **Tailwind CSS 4** con su **CLI standalone**: en desarrollo vía `django-tailwind-cli`; en el
  Dockerfile se descarga el binario y se verifica su checksum SHA-256.
- **htmx 2** servido localmente y configurado sin `eval` ni estilos inline
  (`includeIndicatorStyles: false`, `allowEval: false`, `allowScriptTags: false`).
- **@alpinejs/csp**, la versión de Alpine que no usa `new Function()`. Los componentes se registran con
  `Alpine.data()` en `static/js/app.js` y las directivas solo hacen referencia a propiedades o métodos.
- Modo oscuro con la clase `dark` en `<html>`. Un script externo (`static/js/theme.js`) la aplica antes
  de pintar para evitar el parpadeo.

## Consecuencias
- No hay `node_modules` ni `package.json`, y el CSS compila en segundos.
- Las expresiones de Alpine son más limitadas, así que la lógica vive en componentes JS, que además se
  prueban con más facilidad.
- El look "gamer" se logra con tokens de tema en `assets/css/input.css`.

## Alternativas consideradas
- **Alpine estándar**: requiere `unsafe-eval`, lo que rompe la CSP estricta.
- **Tailwind por CDN**: inyecta estilos inline y crea una dependencia de terceros en tiempo de ejecución.
