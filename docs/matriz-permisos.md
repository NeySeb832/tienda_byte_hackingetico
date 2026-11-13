# Matriz de roles y permisos

> Archivo generado con `python manage.py export_permissions_matrix` a partir de
> `apps/accounts/roles.py`. No se edita a mano; el CI verifica que esté al día.

## Roles

| Rol | Descripción |
|-----|-------------|
| Cliente | Compra, gestiona su cuenta, pedidos, retomas, tickets y reseñas. |
| Vendedor / Cajero | Punto de venta, consulta de stock y clientes, pedidos en tienda. |
| Bodeguero | Inventario, movimientos, recepciones y traslados entre sedes. |
| Técnico de soporte | Tickets de reparación, garantías y evaluación de retomas. |
| Gerente de tienda | Operación de sus sedes, aprobaciones y reportes. |
| Analista de datos | Solo lectura de analítica con datos anonimizados. |
| Administrador | Gestión de la tienda y del personal (excepto superadmins). |
| Superadmin | Configuración del sistema, roles y eventos de seguridad. |

## Permisos por rol

| Permiso | Cliente | Vendedor / Cajero | Bodeguero | Técnico de soporte | Gerente de tienda | Analista de datos | Administrador | Superadmin |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Puede acceder al panel (`accounts.access_panel`) | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Puede gestionar el personal y sus roles (`accounts.manage_staff`) | — | — | — | — | — | — | ✅ | ✅ |
| Puede consultar clientes (CRM) (`accounts.view_customers`) | — | ✅ | — | — | ✅ | — | ✅ | ✅ |
| Can view registro de auditoría (`audit.view_auditlog`) | — | — | — | — | ✅ | — | ✅ | ✅ |
| Can view evento de seguridad (`audit.view_securityevent`) | — | — | — | — | — | — | — | ✅ |
| Can add sede (`inventory.add_store`) | — | — | — | — | — | — | ✅ | ✅ |
| Can change sede (`inventory.change_store`) | — | — | — | — | — | — | ✅ | ✅ |
| Can view sede (`inventory.view_store`) | — | ✅ | ✅ | — | ✅ | — | ✅ | ✅ |

Además de los permisos, el código aplica estas reglas:
- **Alcance por sede:** el personal solo ve sus sedes asignadas; administradores y superadmins ven todas.
- **Datos propios:** un cliente solo accede a sus direcciones, pedidos, tickets y retomas (404 en otro caso).
- **Separación de funciones:** nadie cambia su propio rol, y solo un superadmin gestiona superadmins.
- **MFA obligatorio:** el personal no entra al panel sin la verificación en dos pasos activa.
