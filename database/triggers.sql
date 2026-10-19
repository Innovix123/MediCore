-- Safety-net triggers (SQLite syntax). The Python billing service already checks these rules;
-- the triggers make the database refuse bad data even if someone edits it by hand.

DROP TRIGGER IF EXISTS trg_batch_no_negative;
CREATE TRIGGER trg_batch_no_negative
BEFORE UPDATE OF quantity ON batches
WHEN NEW.quantity < 0
BEGIN
    SELECT RAISE(ABORT, 'Batch quantity cannot go below zero');
END;

DROP TRIGGER IF EXISTS trg_block_expired_sale;
CREATE TRIGGER trg_block_expired_sale
BEFORE INSERT ON invoice_items
WHEN (SELECT expiry_date FROM batches WHERE id = NEW.batch_id) <= DATE('now')
BEGIN
    SELECT RAISE(ABORT, 'Cannot sell an expired batch');
END;
