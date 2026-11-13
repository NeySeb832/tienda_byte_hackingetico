"""National shipping zones (VAT included). Values are configurable later from the panel."""

from decimal import Decimal

from django.db import migrations

# Department DANE codes.
METRO = ["11", "25"]  # Bogotá D.C. and Cundinamarca
MAIN = ["05", "08", "13", "15", "17", "19", "20", "23", "41", "44", "47", "50", "52", "54", "63", "66", "68", "70", "73", "76"]
FREE_FROM = Decimal("300000")


def seed(apps, schema_editor):
    Zone = apps.get_model("shipping", "ShippingZone")
    Department = apps.get_model("core", "Department")
    zones = [
        ("Bogotá y Cundinamarca", Decimal("12000"), FREE_FROM, 1, 2, METRO),
        ("Ciudades principales", Decimal("18000"), FREE_FROM, 2, 4, MAIN),
        ("Resto del país", Decimal("28000"), None, 4, 8, None),
    ]
    used = set(METRO + MAIN)
    for sort, (name, price, free_from, low, high, codes) in enumerate(zones):
        zone, _ = Zone.objects.get_or_create(
            name=name,
            defaults={"price": price, "free_from": free_from, "min_days": low, "max_days": high, "sort": sort},
        )
        departments = (
            Department.objects.filter(code__in=codes)
            if codes is not None
            else Department.objects.exclude(code__in=used)
        )
        zone.departments.set(departments)


class Migration(migrations.Migration):
    dependencies = [("shipping", "0001_initial"), ("core", "0003_seed_geography")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
