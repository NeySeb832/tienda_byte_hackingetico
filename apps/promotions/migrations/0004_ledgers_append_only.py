"""Points and store-credit ledgers can never be edited or deleted."""

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


POINTS = append_only("promotions_loyaltyentry", nullable_fk="created_by_id")
CREDIT = append_only("promotions_creditentry", nullable_fk="created_by_id")


class Migration(migrations.Migration):
    dependencies = [("promotions", "0003_creditentry_loyaltyentry")]

    operations = [migrations.RunSQL(*POINTS), migrations.RunSQL(*CREDIT)]
