"""Gap-free numbering sequences and an append-only order timeline."""

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

TIMELINE_FORWARD, TIMELINE_REVERSE = append_only("orders_orderstatusevent", nullable_fk="actor_id")


class Migration(migrations.Migration):
    dependencies = [("orders", "0001_initial")]

    operations = [
        migrations.RunSQL(
            "CREATE SEQUENCE IF NOT EXISTS orders_order_number_seq START 1001;"
            "CREATE SEQUENCE IF NOT EXISTS orders_invoice_number_seq START 1;",
            "DROP SEQUENCE IF EXISTS orders_order_number_seq; DROP SEQUENCE IF EXISTS orders_invoice_number_seq;",
        ),
        migrations.RunSQL(TIMELINE_FORWARD, TIMELINE_REVERSE),
    ]
