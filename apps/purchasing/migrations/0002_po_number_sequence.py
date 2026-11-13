"""Gap-free numbering for purchase orders."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("purchasing", "0001_initial")]

    operations = [
        migrations.RunSQL(
            "CREATE SEQUENCE IF NOT EXISTS purchasing_po_number_seq START 1;",
            "DROP SEQUENCE IF EXISTS purchasing_po_number_seq;",
        )
    ]
