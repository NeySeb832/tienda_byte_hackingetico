"""Publish version 1.0 of the privacy policy and the terms and conditions."""

from datetime import datetime, timezone

from django.db import migrations

PUBLISHED_AT = datetime(2026, 11, 12, tzinfo=timezone.utc)
DOCUMENTS = [
    ("privacy", "1.0", "Política de tratamiento de datos personales", 'Byte (en adelante, «la tienda») es responsable del tratamiento de los datos personales que recolecta a través de su tienda en línea, sus sedes y su punto de venta, conforme a la Ley 1581 de 2012 y el Decreto 1377 de 2013.\n\nDatos que tratamos: nombres, correo electrónico, teléfono, documento de identidad, direcciones de entrega, historial de compras, retomas y servicios técnicos, y datos técnicos de navegación (dirección IP y eventos de uso seudonimizados).\n\nFinalidades: gestionar tu cuenta y tus pedidos; procesar pagos, envíos, garantías, devoluciones, retomas y servicios técnicos; emitir facturas; prevenir fraude y proteger la seguridad de la plataforma; atender peticiones, quejas y reclamos; y, solo si lo autorizas, enviarte ofertas y novedades.\n\nDerechos del titular: conocer, actualizar y rectificar tus datos; solicitar prueba de la autorización otorgada; ser informado sobre el uso de tus datos; revocar la autorización y solicitar la supresión cuando no exista un deber legal o contractual de conservarlos; acceder gratuitamente a tus datos; y presentar quejas ante la Superintendencia de Industria y Comercio.\n\nCómo ejercer tus derechos: desde «Mi cuenta → Privacidad» puedes descargar una copia de tus datos o solicitar la eliminación de tu cuenta. Las consultas se atienden en un máximo de diez (10) días hábiles y los reclamos en quince (15) días hábiles.\n\nSeguridad: aplicamos cifrado de datos sensibles, control de acceso por roles, autenticación en dos pasos para el personal y registros de auditoría. Nunca almacenamos los datos de tu tarjeta: los pagos los procesa una pasarela certificada.\n\nVigencia: esta versión rige desde su publicación. Si la modificamos, te pediremos aceptar la nueva versión.'),
    ("terms", "1.0", "Términos y condiciones", 'Al comprar en Byte aceptas estas condiciones. Los precios están en pesos colombianos (COP) e incluyen IVA. La disponibilidad de cada producto se confirma al momento del pago.\n\nDerecho de retracto: en compras realizadas a distancia puedes retractarte dentro de los cinco (5) días hábiles siguientes a la entrega, conforme al artículo 47 de la Ley 1480 de 2011, siempre que el producto se devuelva en las mismas condiciones en que lo recibiste.\n\nGarantías: los productos nuevos cuentan con la garantía legal y la del fabricante; los productos usados y reacondicionados tienen la garantía indicada en su ficha según su grado.\n\nEnvíos: los tiempos y costos dependen del departamento y la ciudad de destino y se informan antes de pagar. También puedes recoger tu pedido en nuestras sedes.'),
]


def publish(apps, schema_editor):
    LegalDocument = apps.get_model("cms", "LegalDocument")
    for kind, version, title, body in DOCUMENTS:
        LegalDocument.objects.update_or_create(
            kind=kind,
            version=version,
            defaults={"title": title, "body": body, "published_at": PUBLISHED_AT},
        )


class Migration(migrations.Migration):
    dependencies = [("cms", "0001_initial")]

    operations = [migrations.RunPython(publish, migrations.RunPython.noop)]
