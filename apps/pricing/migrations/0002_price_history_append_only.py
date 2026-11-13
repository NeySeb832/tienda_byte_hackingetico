"""Database-level guarantee that price history rows are never edited or deleted.

The only UPDATE allowed is the ``SET NULL`` of ``changed_by`` when a user row is removed;
any other change raises, so the "before" prices shown to customers cannot be rewritten.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION pricing_pricehistory_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.changed_by_id IS NULL
       AND (NEW.variant_id, NEW.price, NEW.previous_price, NEW.reason, NEW.note, NEW.changed_at)
           IS NOT DISTINCT FROM
           (OLD.variant_id, OLD.price, OLD.previous_price, OLD.reason, OLD.note, OLD.changed_at)
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'pricing_pricehistory is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER pricing_pricehistory_append_only
BEFORE UPDATE OR DELETE ON pricing_pricehistory
FOR EACH ROW EXECUTE FUNCTION pricing_pricehistory_append_only();
"""

REVERSE = """
DROP TRIGGER IF EXISTS pricing_pricehistory_append_only ON pricing_pricehistory;
DROP FUNCTION IF EXISTS pricing_pricehistory_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [("pricing", "0001_initial")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
