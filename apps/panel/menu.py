"""Back-office menu filtered by the permissions of the current user."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MenuItem:
    label: str
    url_name: str
    permission: str


MENU = (
    MenuItem("Resumen", "panel:dashboard", "accounts.access_panel"),
    MenuItem("Pedidos", "panel:orders", "orders.view_order"),
    MenuItem("Punto de venta", "panel:pos", "pos.use_pos"),
    MenuItem("Inventario", "panel:stock", "inventory.view_stockitem"),
    MenuItem("Ajustes de inventario", "panel:adjustments", "inventory.request_adjustment"),
    MenuItem("Traslados", "panel:transfers", "inventory.manage_transfers"),
    MenuItem("Compras", "panel:purchase_orders", "purchasing.view_purchaseorder"),
    MenuItem("Clientes", "panel:customers", "accounts.view_customers"),
    MenuItem("Retomas", "panel:tradeins", "tradein.inspect_tradein"),
    MenuItem("Servicio técnico", "panel:tickets", "services_desk.manage_tickets"),
    MenuItem("Devoluciones", "panel:returns", "orders.receive_return"),
    MenuItem("Precios", "panel:prices", "pricing.change_price"),
    MenuItem("Cupones", "panel:coupons", "promotions.view_coupon"),
    MenuItem("Reportes", "panel:reports", "orders.view_sales_report"),
    MenuItem("Inteligencia de negocio", "panel:bi", "orders.view_sales_report"),
    MenuItem("Personal y roles", "panel:staff", "accounts.manage_staff"),
    MenuItem("Auditoría", "panel:audit", "audit.view_auditlog"),
    MenuItem("Eventos de seguridad", "panel:security", "audit.view_securityevent"),
)


def menu_for(user: Any) -> list[MenuItem]:
    return [item for item in MENU if user.has_perm(item.permission)]
