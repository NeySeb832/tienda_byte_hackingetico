"""Seed Colombian departments and main municipalities (DANE DIVIPOLA codes)."""

from django.db import migrations

DEPARTMENTS = [('05', 'Antioquia'), ('08', 'Atlántico'), ('11', 'Bogotá, D.C.'), ('13', 'Bolívar'), ('15', 'Boyacá'), ('17', 'Caldas'), ('18', 'Caquetá'), ('19', 'Cauca'), ('20', 'Cesar'), ('23', 'Córdoba'), ('25', 'Cundinamarca'), ('27', 'Chocó'), ('41', 'Huila'), ('44', 'La Guajira'), ('47', 'Magdalena'), ('50', 'Meta'), ('52', 'Nariño'), ('54', 'Norte de Santander'), ('63', 'Quindío'), ('66', 'Risaralda'), ('68', 'Santander'), ('70', 'Sucre'), ('73', 'Tolima'), ('76', 'Valle del Cauca'), ('81', 'Arauca'), ('85', 'Casanare'), ('86', 'Putumayo'), ('88', 'Archipiélago de San Andrés, Providencia y Santa Catalina'), ('91', 'Amazonas'), ('94', 'Guainía'), ('95', 'Guaviare'), ('97', 'Vaupés'), ('99', 'Vichada')]
CITIES = [('05001', 'Medellín'), ('05088', 'Bello'), ('05266', 'Envigado'), ('05360', 'Itagüí'), ('05615', 'Rionegro'), ('08001', 'Barranquilla'), ('08758', 'Soledad'), ('11001', 'Bogotá, D.C.'), ('13001', 'Cartagena de Indias'), ('15001', 'Tunja'), ('15238', 'Duitama'), ('15759', 'Sogamoso'), ('17001', 'Manizales'), ('18001', 'Florencia'), ('19001', 'Popayán'), ('20001', 'Valledupar'), ('23001', 'Montería'), ('25175', 'Chía'), ('25269', 'Facatativá'), ('25290', 'Fusagasugá'), ('25307', 'Girardot'), ('25754', 'Soacha'), ('25899', 'Zipaquirá'), ('27001', 'Quibdó'), ('41001', 'Neiva'), ('44001', 'Riohacha'), ('47001', 'Santa Marta'), ('50001', 'Villavicencio'), ('52001', 'Pasto'), ('54001', 'Cúcuta'), ('63001', 'Armenia'), ('66001', 'Pereira'), ('66170', 'Dosquebradas'), ('68001', 'Bucaramanga'), ('68081', 'Barrancabermeja'), ('68276', 'Floridablanca'), ('70001', 'Sincelejo'), ('73001', 'Ibagué'), ('76001', 'Cali'), ('76109', 'Buenaventura'), ('76520', 'Palmira'), ('76834', 'Tuluá'), ('81001', 'Arauca'), ('85001', 'Yopal'), ('86001', 'Mocoa'), ('88001', 'San Andrés'), ('91001', 'Leticia'), ('94001', 'Inírida'), ('95001', 'San José del Guaviare'), ('97001', 'Mitú'), ('99001', 'Puerto Carreño')]


def seed(apps, schema_editor):
    Department = apps.get_model("core", "Department")
    City = apps.get_model("core", "City")
    by_code = {}
    for code, name in DEPARTMENTS:
        by_code[code], _ = Department.objects.update_or_create(code=code, defaults={"name": name})
    for code, name in CITIES:
        City.objects.update_or_create(
            code=code, defaults={"name": name, "department": by_code[code[:2]]}
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0002_department_city")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
