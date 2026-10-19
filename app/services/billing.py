"""Billing. Everything that touches stock happens inside ONE transaction:
if any line fails, nothing is saved and no stock is deducted.
"""
from datetime import date

from app.extensions import db
from app.models.base import utcnow
from app.models.finance import CreditLedger, LoyaltyPoint, Offer
from app.models.medicine import Batch, Medicine
from app.models.order import Reservation
from app.models.sales import Invoice, InvoiceItem, Payment, SaleReturn
from app.services import interaction_checker
from app.services.availability import available_quantity
from app.services.notifications import notify_restock
from app.utils.decorators import current_branch_id

PAYMENT_MODES = ("cash", "upi", "card", "credit")


def _resolve_branch(branch_id):
    """Use the given branch, or fall back to the staff member's current branch.
    Falls back to the main branch (1) when called outside a request (e.g. from a script or a test)."""
    if branch_id:
        return branch_id
    try:
        return current_branch_id()
    except RuntimeError:   # no active Flask request (tests, scripts)
        return 1


class BillingError(Exception):
    """A rule was broken (not enough stock, missing prescription...)."""


class BillingWarning(BillingError):
    """Safety warnings that a pharmacist must acknowledge before the sale continues."""

    def __init__(self, warnings):
        self.warnings = warnings
        super().__init__("; ".join(w["message"] for w in warnings))


def _next_invoice_no():
    return f"INV-{date.today():%y%m%d}-{Invoice.query.count() + 1:05d}"


def _offer_percent(med):
    today = date.today()
    best = 0.0
    for o in Offer.query.filter_by(active=True).all():
        if o.starts_on and o.starts_on > today:
            continue
        if o.ends_on and o.ends_on < today:
            continue
        applies = ((o.medicine_id and o.medicine_id == med.id)
                   or (o.category and o.category == med.category)
                   or (not o.medicine_id and not o.category))
        if applies:
            best = max(best, o.discount_percent)
    return best


def allocate_fefo(med, qty, extra_allowed=0, branch_id=None):
    """Take stock from the batch that expires first, AT THIS BRANCH ONLY. Expired batches are never used."""
    branch_id = _resolve_branch(branch_id)
    available = available_quantity(med.id, branch_id) + extra_allowed
    if available < qty:
        raise BillingError(f"Only {available} of {med.display_name} available at this branch (requested {qty}).")
    batches = (Batch.query.filter(Batch.medicine_id == med.id, Batch.branch_id == branch_id,
                                  Batch.expiry_date > date.today(), Batch.quantity > 0)
               .order_by(Batch.expiry_date, Batch.id).with_for_update().all())
    picks, remaining = [], qty
    for b in batches:
        take = min(b.quantity, remaining)
        b.quantity -= take
        picks.append((b, take))
        remaining -= take
        if remaining == 0:
            break
    if remaining:
        raise BillingError(f"Not enough sellable stock for {med.display_name}.")
    return picks


def create_invoice(cashier_id, lines, payment_mode="cash", customer_id=None, prescription_id=None,
                   discount_pct=0.0, reservation_id=None, order_id=None, acknowledge_warnings=False,
                   family_member_id=None, created_at=None, max_discount=20, branch_id=None):
    """lines = [{'medicine_id': 1, 'quantity': 2}, ...]  -> Invoice. Stock is deducted from `branch_id`
    (or the pharmacist's current branch if not given)."""
    branch_id = _resolve_branch(branch_id)
    if not lines:
        raise BillingError("Add at least one item.")
    if payment_mode not in PAYMENT_MODES:
        raise BillingError("Unknown payment mode.")
    if payment_mode == "credit" and not customer_id:
        raise BillingError("Credit sales need a customer.")
    if not 0 <= float(discount_pct or 0) <= max_discount:
        raise BillingError(f"Discount must be between 0 and {max_discount}%.")

    # merge duplicate medicines
    merged = {}
    for ln in lines:
        qty = int(ln["quantity"])
        if qty <= 0:
            raise BillingError("Quantity must be at least 1.")
        merged[int(ln["medicine_id"])] = merged.get(int(ln["medicine_id"]), 0) + qty

    meds = {m.id: m for m in Medicine.query.filter(Medicine.id.in_(merged), Medicine.deleted_at.is_(None))}
    if len(meds) != len(merged):
        raise BillingError("One of the medicines no longer exists.")

    if any(m.needs_rx for m in meds.values()) and not prescription_id:
        names = ", ".join(m.brand_name for m in meds.values() if m.needs_rx)
        raise BillingError(f"A verified prescription is required for: {names}.")

    warnings = interaction_checker.check(list(merged), customer_id, family_member_id)
    serious = [w for w in warnings if w["severity"] == "major" or w["type"] == "allergy"]
    if serious and not acknowledge_warnings:
        raise BillingWarning(warnings)

    reservation = db.session.get(Reservation, reservation_id) if reservation_id else None
    try:
        invoice = Invoice(invoice_no=_next_invoice_no(), customer_id=customer_id, cashier_id=cashier_id,
                          prescription_id=prescription_id, order_id=order_id, payment_mode=payment_mode,
                          branch_id=branch_id, created_at=created_at or utcnow())
        db.session.add(invoice)

        subtotal = discount = gst_total = 0.0
        for mid, qty in merged.items():
            med = meds[mid]
            extra = reservation.quantity if reservation and reservation.medicine_id == mid \
                and reservation.status == "active" and reservation.branch_id == branch_id else 0
            for batch, taken in allocate_fefo(med, qty, extra, branch_id=branch_id):
                gross = med.mrp * taken
                pct = max(_offer_percent(med), float(discount_pct or 0))
                disc = round(gross * pct / 100, 2)
                net = round(gross - disc, 2)
                gst = round(net * med.gst_percent / (100 + med.gst_percent), 2)   # MRP includes GST
                invoice.items.append(InvoiceItem(
                    medicine_id=mid, batch_id=batch.id, quantity=taken, unit_price=med.mrp,
                    discount_amount=disc, gst_percent=med.gst_percent, gst_amount=gst, line_total=net))
                subtotal += gross
                discount += disc
                gst_total += gst

        invoice.subtotal = round(subtotal, 2)
        invoice.discount = round(discount, 2)
        invoice.gst_amount = round(gst_total, 2)
        invoice.total = round(subtotal - discount, 2)
        db.session.flush()

        db.session.add(Payment(invoice_id=invoice.id, mode=payment_mode, amount=invoice.total))
        if payment_mode == "credit":
            db.session.add(CreditLedger(customer_id=customer_id, invoice_id=invoice.id,
                                        amount=invoice.total, note=f"Credit sale {invoice.invoice_no}"))
        if customer_id and invoice.total >= 100:
            db.session.add(LoyaltyPoint(customer_id=customer_id, points=int(invoice.total // 100),
                                        reason=f"Purchase {invoice.invoice_no}"))
        if reservation and reservation.status == "active":
            reservation.status = "fulfilled"
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    invoice.warnings = warnings
    return invoice


def process_return(invoice_item_id, quantity, reason, user_id):
    """Customer returns unopened stock: refund the line's net price and put units back on the shelf."""
    item = db.session.get(InvoiceItem, invoice_item_id)
    if not item:
        raise BillingError("Invoice line not found.")
    quantity = int(quantity)
    if quantity <= 0 or quantity > item.returnable:
        raise BillingError(f"You can return between 1 and {item.returnable} units of this line.")
    refund = round(item.line_total / item.quantity * quantity, 2)
    item.batch.quantity += quantity
    item.returned_qty = (item.returned_qty or 0) + quantity
    ret = SaleReturn(invoice_item_id=item.id, quantity=quantity, reason=reason,
                     refund_amount=refund, created_by=user_id)
    db.session.add(ret)
    db.session.commit()
    notify_restock(item.medicine_id)
    return ret
