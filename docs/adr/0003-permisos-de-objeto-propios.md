# ADR-0003: Permisos a nivel de objeto con servicio propio

- **Estado:** Aceptada
- **Fecha:** 2026-11-12

## Contexto
Los permisos por objeto que necesita Byte son **relacionales**:
- Un cliente solo ve *sus* pedidos, direcciones, tickets y retomas.
- Un gerente solo ve las *sedes que tiene asignadas*.
- Quien crea un ajuste o un descuento alto no puede aprobarlo.

No hay casos de permisos concedidos manualmente fila por fila.

## Decisión
- Los grupos y permisos de Django definen el "qué" (rol × acción). Un **servicio propio** define el
  "sobre cuáles" (alcance).
- Cada selector recibe al usuario y devuelve un queryset ya filtrado por dueño o sede. Si el objeto no
  está en el queryset, la respuesta es 404, así no se revela que existe.
- Los mixins `RoleRequiredMixin` y `ObjectPermissionMixin` (Fase 2) combinan ambas comprobaciones y se
  usan en todas las vistas del panel y en los endpoints.
- La separación de funciones se valida en los servicios y con constraints `CHECK` en la BD.

## Consecuencias
- Denegar por defecto: lo que no está en el queryset del usuario no existe para él.
- No hay una tabla de permisos por fila que mantener sincronizada. Con `django-guardian`, olvidar
  asignar o revocar una fila haría que el control fallara *abierto*.
- Los tests de IDOR cambian el UUID por el de otro usuario o sede y esperan 404 o 403.

## Alternativas consideradas
- **django-guardian 3.5**: es una buena librería, pero resuelve ACLs arbitrarias por fila, que aquí no
  se necesitan, y añade una tabla y señales que mantener.
- **django-rules**: añade una dependencia para algo que se expresa en pocas líneas con querysets.
