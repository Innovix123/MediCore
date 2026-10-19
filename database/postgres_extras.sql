-- OPTIONAL: only for PostgreSQL. Not run automatically and not covered by the tests.

-- Typo-tolerant search (fast ILIKE '%text%' and similarity())
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS ix_med_brand_trgm ON medicines USING gin (brand_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_med_generic_trgm ON medicines USING gin (generic_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_med_comp_trgm ON medicines USING gin (composition gin_trgm_ops);

-- Example: block negative stock
CREATE OR REPLACE FUNCTION batch_no_negative() RETURNS trigger AS $$
BEGIN
  IF NEW.quantity < 0 THEN RAISE EXCEPTION 'Batch quantity cannot go below zero'; END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_batch_no_negative ON batches;
CREATE TRIGGER trg_batch_no_negative BEFORE UPDATE OF quantity ON batches
FOR EACH ROW EXECUTE FUNCTION batch_no_negative();
