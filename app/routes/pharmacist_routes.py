from datetime import date

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request,
                   send_file, session, url_for)
from flask_login import current_user

from app.extensions import db
from app.models import (Branch, CounselingNote, Customer, Delivery, Doctor, Invoice, InvoiceItem, Medicine,
                        Order, Prescription, PrescriptionUpload, Shift)
from app.models.base import utcnow
from app.services import billing, reports
from app.services.availability import available_quantities, find_medicines
from app.utils.decorators import CLINICAL, STAFF, current_branch_id, role_required
from app.utils.pdf_export import invoice_pdf
from app.utils.validators import to_date, to_float, to_int

pharmacist_bp = Blueprint("pharmacist", __name__, url_prefix="/pharmacist")
staff_only = role_required(*STAFF)
clinical_only = role_required(*CLINICAL)


def staff_branches():
    """Branches this staff member is allowed to work from (their own pharmacy's active branches)."""
    q = Branch.query.filter_by(active=True)
    if current_user.is_authenticated and current_user.pharmacy_id:
        q = q.filter_by(pharmacy_id=current_user.pharmacy_id)
    return q.order_by(Branch.name).all()


@pharmacist_bp.route("/branch/switch", methods=["POST"])
@staff_only
def switch_branch():
    branch_id = to_int(request.form.get("branch_id"), 0)
    allowed = {b.id for b in staff_branches()}
    if branch_id in allowed:
        session["branch_id"] = branch_id
        flash(f"Now working from {db.session.get(Branch, branch_id).name}.", "ok")
    else:
        flash("You don't have access to that branch.", "error")
    return redirect(request.referrer or url_for("pharmacist.pos"))


def get_or_create_doctor(name, reg_no=""):
    name = (name or "").strip()
    if not name:
        return None
    doc = Doctor.query.filter_by(name=name).first()
    if not doc:
        doc = Doctor(name=name, registration_no=reg_no)
        db.session.add(doc)
        db.session.flush()
    return doc


# ---------------- point of sale ----------------
@pharmacist_bp.route("/pos")
@staff_only
def pos():
    customers = Customer.query.filter(Customer.deleted_at.is_(None)).order_by(Customer.name).all()
    branches = staff_branches()
    current_branch = db.session.get(Branch, current_branch_id())
    return render_template("pharmacist/pos.html", customers=customers, branches=branches,
                           current_branch=current_branch, max_discount=current_app.config["MAX_MANUAL_DISCOUNT"])


@pharmacist_bp.route("/lookup")
@staff_only
def lookup():
    """Staff-only medicine lookup (barcode or name) with exact stock numbers AT THIS BRANCH."""
    meds = find_medicines(request.args.get("q", ""), limit=8)
    avail = available_quantities([m.id for m in meds], current_branch_id())
    return jsonify([{"id": m.id, "name": m.display_name, "generic": m.generic_name, "price": m.mrp,
                     "qty": avail[m.id], "rx": m.needs_rx, "schedule": m.schedule} for m in meds])


@pharmacist_bp.route("/pos/checkout", methods=["POST"])
@staff_only
def pos_checkout():
    data = request.get_json(silent=True) or {}
    lines = [{"medicine_id": i.get("medicine_id"), "quantity": i.get("quantity")} for i in data.get("items", [])]
    customer_id = to_int(data.get("customer_id")) or None
    try:
        rx_id = None
        if data.get("rx_verified"):
            doctor = get_or_create_doctor(data.get("doctor_name"), data.get("doctor_reg", ""))
            if not doctor:
                raise billing.BillingError("Enter the prescribing doctor's name.")
            rx = Prescription(customer_id=customer_id, doctor_id=doctor.id, issued_on=date.today(),
                              verified_by=current_user.id, notes="Verified at counter")
            db.session.add(rx)
            db.session.flush()
            rx_id = rx.id
        invoice = billing.create_invoice(
            current_user.id, lines, payment_mode=data.get("payment_mode", "cash"), customer_id=customer_id,
            prescription_id=rx_id, discount_pct=to_float(data.get("discount_pct"), 0.0),
            reservation_id=to_int(data.get("reservation_id")),
            acknowledge_warnings=bool(data.get("acknowledge")),
            max_discount=current_app.config["MAX_MANUAL_DISCOUNT"] if current_user.role_name != "admin" else 100)
    except billing.BillingWarning as w:
        db.session.rollback()
        return jsonify({"ok": False, "needs_ack": True, "warnings": w.warnings}), 409
    except (billing.BillingError, KeyError, ValueError, TypeError) as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "invoice_id": invoice.id, "invoice_no": invoice.invoice_no, "total": invoice.total,
                    "warnings": invoice.warnings, "url": url_for("pharmacist.invoice", invoice_id=invoice.id)})


# ---------------- invoices, counseling, returns ----------------
@pharmacist_bp.route("/invoice/<int:invoice_id>")
@staff_only
def invoice(invoice_id):
    inv = db.session.get(Invoice, invoice_id) or abort(404)
    notes = CounselingNote.query.filter_by(invoice_id=inv.id).order_by(CounselingNote.created_at).all()
    return render_template("pharmacist/invoice.html", inv=inv, notes=notes)


@pharmacist_bp.route("/invoice/<int:invoice_id>/pdf")
@staff_only
def invoice_pdf_view(invoice_id):
    inv = db.session.get(Invoice, invoice_id) or abort(404)
    return send_file(invoice_pdf(inv), mimetype="application/pdf", download_name=f"{inv.invoice_no}.pdf")


@pharmacist_bp.route("/invoice/<int:invoice_id>/note", methods=["POST"])
@clinical_only
def add_note(invoice_id):
    inv = db.session.get(Invoice, invoice_id) or abort(404)
    text = request.form.get("note", "").strip()
    if text:
        db.session.add(CounselingNote(invoice_id=inv.id, pharmacist_id=current_user.id, note=text))
        db.session.commit()
        flash("Counseling note saved.", "ok")
    return redirect(url_for("pharmacist.invoice", invoice_id=inv.id))


@pharmacist_bp.route("/returns", methods=["GET", "POST"])
@staff_only
def returns():
    if request.method == "POST":
        try:
            ret = billing.process_return(to_int(request.form.get("invoice_item_id"), 0), request.form.get("quantity"),
                                         request.form.get("reason", "").strip(), current_user.id)
            flash(f"Return recorded. Refund Rs {ret.refund_amount:,.2f}. Stock restored.", "ok")
        except (billing.BillingError, ValueError) as e:
            flash(str(e), "error")
        return redirect(url_for("pharmacist.returns", invoice_no=request.form.get("invoice_no", "")))
    inv = None
    q = request.args.get("invoice_no", "").strip()
    if q:
        inv = Invoice.query.filter_by(invoice_no=q).first()
        if not inv:
            flash("No invoice with that number.", "error")
    return render_template("pharmacist/returns.html", inv=inv, q=q)


# ---------------- prescription verification ----------------
@pharmacist_bp.route("/verification")
@clinical_only
def verification():
    pending = PrescriptionUpload.query.filter_by(status="pending").order_by(PrescriptionUpload.uploaded_at).all()
    recent = (PrescriptionUpload.query.filter(PrescriptionUpload.status != "pending")
              .order_by(PrescriptionUpload.reviewed_at.desc()).limit(10).all())
    return render_template("pharmacist/verification.html", pending=pending, recent=recent)


@pharmacist_bp.route("/verification/<int:upload_id>", methods=["POST"])
@clinical_only
def verify(upload_id):
    up = db.session.get(PrescriptionUpload, upload_id) or abort(404)
    action, reason = request.form.get("action"), request.form.get("reason", "").strip()
    if up.status != "pending":
        flash("That prescription was already reviewed.", "error")
    elif action == "approve":
        up.status = "approved"
        for o in Order.query.filter_by(prescription_upload_id=up.id, status="awaiting_prescription"):
            o.status = "placed"
        flash("Prescription approved. Linked orders are now ready to pack.", "ok")
    elif action == "reject" and reason:
        up.status, up.reject_reason = "rejected", reason[:200]
        for o in Order.query.filter_by(prescription_upload_id=up.id, status="awaiting_prescription"):
            o.status = "cancelled"
        flash("Prescription rejected and the customer's linked orders were cancelled.", "ok")
    else:
        flash("Give a reason when rejecting.", "error")
        return redirect(url_for("pharmacist.verification"))
    up.reviewed_by, up.reviewed_at = current_user.id, utcnow()
    db.session.commit()
    return redirect(url_for("pharmacist.verification"))


# ---------------- online orders ----------------
def _next_status(order):
    return {"placed": "packed",
            "packed": "out_for_delivery" if order.fulfilment == "delivery" else "ready_for_pickup",
            "out_for_delivery": "delivered", "ready_for_pickup": "delivered"}.get(order.status)


@pharmacist_bp.route("/orders")
@staff_only
def orders():
    rows = (Order.query.filter(Order.status.notin_(("delivered", "cancelled")))
            .order_by(Order.created_at).all())
    return render_template("pharmacist/orders.html", orders=rows, next_status=_next_status)


@pharmacist_bp.route("/orders/<int:order_id>/advance", methods=["POST"])
@clinical_only
def advance_order(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    nxt = _next_status(order)
    if not nxt:
        flash("Nothing to do for this order yet.", "error")
        return redirect(url_for("pharmacist.orders"))
    if nxt == "packed":      # bill the order: deducts stock (FEFO) and runs safety checks
        rx_id = None
        if order.prescription_upload and order.prescription_upload.status == "approved":
            up = order.prescription_upload
            doctor = get_or_create_doctor(up.doctor_name)
            rx = Prescription(customer_id=order.customer_id, doctor_id=doctor.id if doctor else None,
                              upload_id=up.id, issued_on=date.today(), verified_by=up.reviewed_by)
            db.session.add(rx)
            db.session.flush()
            rx_id = rx.id
        try:
            billing.create_invoice(current_user.id, [{"medicine_id": i.medicine_id, "quantity": i.quantity}
                                                     for i in order.items],
                                   customer_id=order.customer_id, prescription_id=rx_id, order_id=order.id,
                                   acknowledge_warnings=bool(request.form.get("acknowledge")))
        except billing.BillingWarning as w:
            db.session.rollback()
            flash("Safety warning: " + " | ".join(x["message"] for x in w.warnings) +
                  " Tick 'Acknowledge warnings' to pack anyway.", "error")
            return redirect(url_for("pharmacist.orders"))
        except billing.BillingError as e:
            db.session.rollback()
            flash(str(e), "error")
            return redirect(url_for("pharmacist.orders"))
    if nxt == "out_for_delivery":
        d = order.delivery or Delivery(order_id=order.id)
        d.driver_name, d.driver_phone = request.form.get("driver_name", "").strip(), request.form.get("driver_phone", "").strip()
        d.status = "on_the_way"
        db.session.add(d)
    order.status = nxt
    db.session.commit()
    flash(f"Order #{order.id} is now: {nxt.replace('_', ' ')}.", "ok")
    return redirect(url_for("pharmacist.orders"))


@pharmacist_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@clinical_only
def cancel_order(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    if order.status in ("placed", "awaiting_prescription"):
        order.status = "cancelled"
        db.session.commit()
        flash("Order cancelled.", "ok")
    else:
        flash("Packed orders are already billed. Use Returns instead.", "error")
    return redirect(url_for("pharmacist.orders"))


# ---------------- shifts and end-of-day ----------------
@pharmacist_bp.route("/shift", methods=["POST"])
@staff_only
def shift():
    open_shift = Shift.query.filter_by(user_id=current_user.id, clock_out=None).first()
    if open_shift:
        open_shift.clock_out = utcnow()
        flash("Clocked out.", "ok")
    else:
        db.session.add(Shift(user_id=current_user.id))
        flash("Clocked in.", "ok")
    db.session.commit()
    return redirect(request.referrer or url_for("pharmacist.pos"))


@pharmacist_bp.route("/daily-summary", methods=["GET", "POST"])
@staff_only
def daily_summary():
    day = to_date(request.values.get("day"), date.today())
    summary = reports.daily_sales(day, current_branch_id())
    counted = to_float(request.form.get("counted_cash")) if request.method == "POST" else None
    expected = summary["by_mode"].get("cash", 0.0)
    return render_template("pharmacist/daily_summary.html", s=summary, counted=counted, expected=expected,
                           diff=None if counted is None else round(counted - expected, 2))
