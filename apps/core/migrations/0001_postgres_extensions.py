"""Enable PostgreSQL extensions used by search (pg_trgm) and accent-insensitive matching."""

from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [TrigramExtension(), UnaccentExtension()]
