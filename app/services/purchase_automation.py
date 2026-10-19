"""Auto-generate purchase orders for medicines that fell to their reorder level."""
from datetime import date, timedelta

from app.extensions import db
from app.models.medicine import Batch, Medicine
from app.models.supplier import GoodsReceipt, PurchaseOrder, PurchaseOrderItem, Supplier
from app.services.availability import available_quantities
from app.services.forecasting import forecast_next_30_days
from app.services.notifications import notify_restock


def reorder_suggestions(pharmacy_id=None):
    """Medicines at or below reorder level, counting stock across every branch of `pharmacy_id`
    (or everywhere, if not given)."""
    meds = Medicine.query.filter(Medicine.deleted_at.is_(None)).all()
    avail = available_quantities([m.id for m in meds], pharmacy_id=pharmacy_id)
    out = []
    for m in meds:
        current = avail[m.id]
        if current <= m.reorder_level:
            target = max(m.reorder_level * 2, forecast_next_30_days(m.id))
            out.append({"medicine": m, "current": current, "suggested": int(target - current) or m.reorder_level})
    return out


def _last_cost(medicine_id):
    b = (Batch.query.filter_by(medicine_id=medicine_id).order_by(Batch.received_on.desc(), Batch.id.desc()).first())
    return b.purchase_price if b and b.purchase_price else 0


def generate_purchase_orders(user_id=None, pharmacy_id=None):
    """One DRAFT purchase order per supplier, for THIS pharmacy only. Medicines already on an
    open PO (for this pharmacy) are skipped."""
    open_pos = PurchaseOrder.query.filter(PurchaseOrder.status.in_(("draft", "sent")))
    if pharmacy_id:
        open_pos = open_pos.filter(PurchaseOrder.pharmacy_id == pharmacy_id)
    open_ids = {i.medicine_id for po in open_pos.all() for i in po.items}

    supplier_q = Supplier.query
    if pharmacy_id:
        supplier_q = supplier_q.filter_by(pharmacy_id=pharmacy_id)
    default_supplier = supplier_q.order_by(Supplier.id).first()

    by_supplier, created = {}, []
    for s in reorder_suggestions(pharmacy_id=pharmacy_id):
        m = s["medicine"]
        if m.id in open_ids:
            continue
        supplier_id = m.preferred_supplier_id or (default_supplier.id if default_supplier else None)
        if supplier_id:
            by_supplier.setdefault(supplier_id, []).append(s)
    for supplier_id, rows in by_supplier.items():
        supplier = db.session.get(Supplier, supplier_id)
        po = PurchaseOrder(pharmacy_id=pharmacy_id or supplier.pharmacy_id,
                           po_number=f"PO-{date.today():%y%m%d}-{PurchaseOrder.query.count() + 1:04d}",
                           supplier_id=supplier_id, auto_generated=True, created_by=user_id,
                           expected_on=date.today() + timedelta(days=3))
        for s in rows:
            po.items.append(PurchaseOrderItem(medicine_id=s["medicine"].id, quantity=s["suggested"],
                                              unit_cost=_last_cost(s["medicine"].id)))
        db.session.add(po)
        db.session.flush()
        created.append(po)
    db.session.commit()
    return created


def receive_purchase_order(po_id, user_id, item_rows, supplier_invoice_no="", branch_id=1):
    """item_rows = [{'item_id', 'batch_no', 'expiry_date', 'quantity'}] -> creates/updates batches."""
    po = db.session.get(PurchaseOrder, po_id)
    if not po or po.status == "received":
        raise ValueError("Purchase order not found or already received.")
    by_id = {i.id: i for i in po.items}
    amount, meds = 0.0, []
    for row in item_rows:
        item = by_id[row["item_id"]]
        qty = int(row["quantity"])
        if qty <= 0:
            continue
        batch = Batch.query.filter_by(medicine_id=item.medicine_id, batch_no=row["batch_no"],
                                      branch_id=branch_id).first()
        if batch:
            batch.quantity += qty
        else:
            db.session.add(Batch(medicine_id=item.medicine_id, batch_no=row["batch_no"], branch_id=branch_id,
                                 expiry_date=row["expiry_date"], quantity=qty, purchase_price=item.unit_cost,
                                 supplier_id=po.supplier_id, received_on=date.today()))
        amount += qty * item.unit_cost
        meds.append(item.medicine_id)
    po.status = "received"
    db.session.add(GoodsReceipt(po_id=po.id, supplier_id=po.supplier_id, supplier_invoice_no=supplier_invoice_no,
                                received_by=user_id, amount=round(amount, 2),
                                due_date=date.today() + timedelta(days=po.supplier.payment_terms_days or 30)))
    db.session.commit()
    for mid in set(meds):
        notify_restock(mid)
    return po
