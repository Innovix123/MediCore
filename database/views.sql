-- Reporting views (SQLite syntax). Applied automatically by `flask init-db`.
-- PostgreSQL: replace DATE('now') with CURRENT_DATE and DATE('now','+90 day') with CURRENT_DATE + 90.

DROP VIEW IF EXISTS v_low_stock;
DROP VIEW IF EXISTS v_near_expiry;
DROP VIEW IF EXISTS v_daily_sales;
DROP VIEW IF EXISTS v_dead_stock;
DROP VIEW IF EXISTS v_stock_summary;

-- Sellable quantity per medicine (expired batches are ignored)
CREATE VIEW v_stock_summary AS
SELECT m.id AS medicine_id, m.brand_name, m.generic_name, m.reorder_level,
       COALESCE(SUM(CASE WHEN b.expiry_date > DATE('now') AND b.quantity > 0 THEN b.quantity END), 0) AS sellable_qty
FROM medicines m
LEFT JOIN batches b ON b.medicine_id = m.id
WHERE m.deleted_at IS NULL
GROUP BY m.id;

CREATE VIEW v_low_stock AS
SELECT * FROM v_stock_summary WHERE sellable_qty <= reorder_level;

-- Batches expiring within 90 days, earliest first (FEFO)
CREATE VIEW v_near_expiry AS
SELECT b.id AS batch_id, m.brand_name, b.batch_no, b.expiry_date, b.quantity,
       CAST(julianday(b.expiry_date) - julianday('now') AS INTEGER) AS days_left
FROM batches b JOIN medicines m ON m.id = b.medicine_id
WHERE b.quantity > 0 AND b.expiry_date > DATE('now') AND b.expiry_date <= DATE('now', '+90 day')
ORDER BY b.expiry_date;

CREATE VIEW v_daily_sales AS
SELECT DATE(created_at) AS sale_date, COUNT(*) AS invoices, SUM(total) AS revenue, SUM(gst_amount) AS gst
FROM invoices GROUP BY DATE(created_at);

-- In stock but nothing sold in 90 days
CREATE VIEW v_dead_stock AS
SELECT s.* FROM v_stock_summary s
WHERE s.sellable_qty > 0
  AND NOT EXISTS (SELECT 1 FROM invoice_items ii JOIN invoices i ON i.id = ii.invoice_id
                  WHERE ii.medicine_id = s.medicine_id AND i.created_at >= DATE('now', '-90 day'));
