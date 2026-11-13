"""Database-level guarantee that audit rows are never updated or deleted (A09)."""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION audit_auditlog_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditlog is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_auditlog_append_only
BEFORE UPDATE OR DELETE ON audit_auditlog
FOR EACH ROW EXECUTE FUNCTION audit_auditlog_append_only();
"""

REVERSE = """
DROP TRIGGER IF EXISTS audit_auditlog_append_only ON audit_auditlog;
DROP FUNCTION IF EXISTS audit_auditlog_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
