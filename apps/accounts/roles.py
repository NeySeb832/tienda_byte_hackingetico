"""Roles of Byte as Django groups and the permissions each one grants.

Single source of truth used by ``setup_roles`` (idempotent) and by
``export_permissions_matrix`` (docs/matriz-permisos.md). New phases extend
``ROLE_PERMISSIONS`` with their own permissions.
"""

CUSTOMER = "Cliente"
SELLER = "Vendedor / Cajero"
WAREHOUSE = "Bodeguero"
TECHNICIAN = "Técnico de soporte"
MANAGER = "Gerente de tienda"
ANALYST = "Analista de datos"
ADMIN = "Administrador"
SUPERADMIN = "Superadmin"

ALL_ROLES = (CUSTOMER, SELLER, WAREHOUSE, TECHNICIAN, MANAGER, ANALYST, ADMIN, SUPERADMIN)
STAFF_ROLES = (SELLER, WAREHOUSE, TECHNICIAN, MANAGER, ANALYST, ADMIN, SUPERADMIN)
PRIVILEGED_ROLES = (ADMIN, SUPERADMIN)

ROLE_DESCRIPTIONS = {
    CUSTOMER: "Compra, gestiona su cuenta, pedidos, retomas, tickets y reseñas.",
    SELLER: "Punto de venta, consulta de stock y clientes, pedidos en tienda.",
    WAREHOUSE: "Inventario, movimientos, recepciones y traslados entre sedes.",
    TECHNICIAN: "Tickets de reparación, garantías y evaluación de retomas.",
    MANAGER: "Operación de sus sedes, aprobaciones y reportes.",
    ANALYST: "Solo lectura de analítica con datos anonimizados.",
    ADMIN: "Gestión de la tienda y del personal (excepto superadmins).",
    SUPERADMIN: "Configuración del sistema, roles y eventos de seguridad.",
}

PANEL = "accounts.access_panel"
_ADMIN = frozenset(
    {
        PANEL,
        "accounts.view_customers",
        "accounts.manage_staff",
        "inventory.view_store",
        "inventory.add_store",
        "inventory.change_store",
        "audit.view_auditlog",
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    CUSTOMER: frozenset(),
    SELLER: frozenset({PANEL, "accounts.view_customers", "inventory.view_store"}),
    WAREHOUSE: frozenset({PANEL, "inventory.view_store"}),
    TECHNICIAN: frozenset({PANEL}),
    MANAGER: frozenset(
        {PANEL, "accounts.view_customers", "inventory.view_store", "audit.view_auditlog"}
    ),
    ANALYST: frozenset({PANEL}),
    ADMIN: _ADMIN,
    SUPERADMIN: _ADMIN | {"audit.view_securityevent"},
}

# Roles a user may assign, depending on whether they are a superuser.
ASSIGNABLE_BY_ADMIN = tuple(role for role in ALL_ROLES if role != SUPERADMIN)
