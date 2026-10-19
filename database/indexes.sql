-- Extra indexes (names, expiry and invoice dates are also indexed by the models).
CREATE INDEX IF NOT EXISTS ix_batches_med_expiry ON batches (medicine_id, expiry_date);
CREATE INDEX IF NOT EXISTS ix_invoice_items_med ON invoice_items (medicine_id, invoice_id);
CREATE INDEX IF NOT EXISTS ix_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS ix_reservations_active ON reservations (medicine_id, status, expires_at);
