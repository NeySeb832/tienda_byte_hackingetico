"""PDF of the (test) electronic invoice, drawn with ReportLab. No user HTML is rendered."""

import io
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.core.money import format_cop
from apps.orders.models import Order

SELLER = "Byte S.A.S. · NIT 900.000.000-0 (ficticio) · Bogotá, Colombia"


def render_invoice(order: Order) -> bytes:
    invoice = order.invoice
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter, pageCompression=1)
    pdf.setTitle(f"Factura {invoice.number}")
    width, height = letter

    # Mandatory test notice (spec): visible watermark and header.
    pdf.saveState()
    pdf.setFillColor(colors.Color(0.85, 0.1, 0.2, alpha=0.12))
    pdf.setFont("Helvetica-Bold", 60)
    pdf.translate(width / 2, height / 2)
    pdf.rotate(35)
    pdf.drawCentredString(0, 0, "DOCUMENTO DE PRUEBA")
    pdf.restoreState()

    y = height - 20 * mm
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(20 * mm, y, "BYTE")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(20 * mm, y - 6 * mm, SELLER)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(width - 20 * mm, y, f"Factura electrónica de venta {invoice.number}")
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(width - 20 * mm, y - 6 * mm, f"Emitida: {invoice.issued_at:%Y-%m-%d %H:%M}")
    pdf.drawRightString(width - 20 * mm, y - 11 * mm, f"Pedido: {order.number}")
    pdf.setFillColor(colors.red)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(
        20 * mm,
        y - 16 * mm,
        "Documento de prueba generado en ambiente sandbox: no tiene validez fiscal ante la DIAN.",
    )
    pdf.setFillColor(colors.black)

    y -= 28 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(20 * mm, y, "Cliente")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(20 * mm, y - 5 * mm, order.email)
    if order.address_snapshot:
        address = json.loads(order.address_snapshot)
        pdf.drawString(
            20 * mm, y - 10 * mm, f"{address['recipient']} · {address['line1']}, {address['city']}"
        )
    else:
        store = order.pickup_store
        pdf.drawString(20 * mm, y - 10 * mm, f"Recoge en tienda: {store.name if store else ''}")

    y -= 22 * mm
    pdf.setFont("Helvetica-Bold", 9)
    for x, label in ((20, "SKU"), (55, "Producto"), (140, "Cant."), (160, "Valor unit.")):
        pdf.drawString(x * mm, y, label)
    pdf.drawRightString(width - 20 * mm, y, "Total")
    pdf.setFont("Helvetica", 9)
    for line in order.lines.all():
        y -= 6 * mm
        pdf.drawString(20 * mm, y, line.sku[:18])
        pdf.drawString(55 * mm, y, f"{line.name} {line.variant_label}"[:48])
        pdf.drawString(140 * mm, y, str(line.quantity))
        pdf.drawString(160 * mm, y, format_cop(line.unit_price))
        pdf.drawRightString(width - 20 * mm, y, format_cop(line.line_total))

    y -= 12 * mm
    rows = [
        ("Subtotal", order.subtotal),
        ("Descuento", -order.discount_total),
        ("Envío", order.shipping_total),
        ("IVA incluido (19 %)", order.tax_total),
        ("Total pagado", order.total),
    ]
    for label, amount in rows:
        pdf.setFont("Helvetica-Bold" if label == "Total pagado" else "Helvetica", 10)
        pdf.drawString(130 * mm, y, label)
        pdf.drawRightString(width - 20 * mm, y, format_cop(amount))
        y -= 6 * mm

    pdf.setFont("Helvetica", 7)
    pdf.drawString(20 * mm, 20 * mm, f"CUFE (simulado): {invoice.cufe}")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
