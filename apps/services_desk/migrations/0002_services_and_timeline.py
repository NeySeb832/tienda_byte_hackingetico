"""Technical services from the master price list and an append-only ticket timeline."""

from decimal import Decimal

from django.db import migrations


def append_only(table: str, *, nullable_fk: str) -> tuple[str, str]:
    function = f"{table}_append_only"
    forward = f"""
CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.{nullable_fk} IS NULL AND OLD.{nullable_fk} IS NOT NULL THEN
        RETURN NEW;  -- SET NULL when the referenced user is removed
    END IF;
    RAISE EXCEPTION '{table} is append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER {function} BEFORE UPDATE OR DELETE ON {table}
FOR EACH ROW EXECUTE FUNCTION {function}();
"""
    reverse = f"DROP TRIGGER IF EXISTS {function} ON {table}; DROP FUNCTION IF EXISTS {function}();"
    return forward, reverse


TIMELINE = append_only("services_desk_ticketevent", nullable_fk="actor_id")

SERVICES = [
    ("Cambio de joystick", "Controles de PS5 y Xbox Series, por unidad", "35000", 1),
    ("Cambio de joystick en Joy-Con", "Nintendo Switch, por unidad", "35000", 1),
    ("Cambio de joystick en controles pro", "DualSense Edge y Xbox Elite, por unidad", "45000", 1),
    ("Cambio de joystick en controles retro", "Xbox clásica a Xbox One y PS2 a PS4, por unidad", "25000", 1),
    ("Cambio de joystick en control de GameCube", "Por unidad", "30000", 1),
    ("Cambio de joystick en Wii U GamePad", "Por unidad", "45000", 2),
    ("Mantenimiento preventivo", "PS4 y Xbox One: limpieza interna y cambio de pasta térmica", "90000", 2),
]
HOME = {"Cambio de joystick", "Cambio de joystick en Joy-Con", "Cambio de joystick en controles pro", "Mantenimiento preventivo"}


def seed(apps, schema_editor):
    Service = apps.get_model("services_desk", "TechnicalService")
    for sort, (name, detail, price, days) in enumerate(SERVICES):
        Service.objects.get_or_create(
            name=name, defaults={"detail": detail, "price": Decimal(price), "estimated_days": days, "sort": sort if name in HOME else 100 + sort}
        )


class Migration(migrations.Migration):
    dependencies = [("services_desk", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop), migrations.RunSQL(*TIMELINE)]
