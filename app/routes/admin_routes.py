import csv
import io
from datetime import date, datetime, time, timedelta

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import (AuditLog, Batch, Branch, CreditLedger, Customer, Expense, GoodsReceipt, Invoice,
                        Medicine, Offer, PurchaseOrder, Role, Shift, StockWriteoff, Supplier, SupplierReturn, User)
from app.services import forecasting, purchase_automation, reports, scheduled_drugs
from app.services.availability import available_quantities, stock_status
from app.utils.decorators import current_branch_id, role_required
from app.utils.validators import to_date, to_float, to_int

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_only = role_required("admin")


def pharmacy_branches():
    q = Branch.query
    if current_user.pharmacy_id:
        q = q.filter_by(pharmacy_id=current_user.pharmacy_id)
    return q.order_by(Branch.name).all()


def _generic_page(title, headers, rows, fields=None, action=None, intro="", button="Save"):
    return render_template("admin/list_page.html", title=title, headers=headers, rows=rows, fields=fields or [],
                           action=action, intro=intro, button=button)


# ---------------- dashboard ----------------
@admin_bp.route("/")
@admin_only
def dashboard():
    trend = reports.sales_trend(14)
    peak = max((v for _, v in trend), default=0) or 1
    return render_template("admin/dashboard.html", k=reports.dashboard_kpis(), trend=trend, peak=peak,
                           top_rows=[[n, int(u), f"Rs {float(v):,.2f}"] for n, u, v in reports.top_sellers()], unmet=reports.unmet_demand()[:5])


# ---------------- inventory ----------------
@admin_bp.route("/inventory")
@admin_only
def inventory():
    q = request.args.get("q", "").strip()
    query = Medicine.query.filter(Medicine.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(Medicine.brand_name.ilike(like) | Medicine.generic_name.ilike(like))
    meds = query.order_by(Medicine.brand_name).all()
    branch_id = current_branch_id()
    avail = available_quantities([m.id for m in meds], branch_id)
    rows = [{"m": m, "qty": avail[m.id], "status": stock_status(avail[m.id], m.reorder_level)} for m in meds]
    current_branch = db.session.get(Branch, branch_id)
    return render_template("admin/inventory.html", rows=rows, q=q, current_branch=current_branch,
                           branches=pharmacy_branches())


def _fill_medicine(m, f):
    m.brand_name, m.generic_name = f["brand_name"].strip(), f["generic_name"].strip()
    m.composition = f.get("composition", "").strip() or m.generic_name
    m.strength, m.form, m.category = f.get("strength", ""), f.get("form", "Tablet"), f.get("category", "General")
    m.schedule = f.get("schedule", "OTC")
    m.requires_prescription = bool(f.get("requires_prescription")) or m.schedule != "OTC"
    m.mrp, m.gst_percent = to_float(f.get("mrp"), 0.0), to_float(f.get("gst_percent"), 12.0)
    m.reorder_level = to_int(f.get("reorder_level"), 20, minimum=0)
    m.criticality = f.get("criticality", "D")
    m.barcode = f.get("barcode", "").strip() or None
    m.preferred_supplier_id = to_int(f.get("preferred_supplier_id")) or None
    m.uses, m.side_effects = f.get("uses", ""), f.get("side_effects", "")


@admin_bp.route("/inventory/new", methods=["GET", "POST"])
@admin_bp.route("/inventory/<int:medicine_id>/edit", methods=["GET", "POST"])
@admin_only
def medicine_form(medicine_id=None):
    med = db.session.get(Medicine, medicine_id) if medicine_id else None
    if medicine_id and not med:
        abort(404)
    if request.method == "POST":
        f = request.form
        if not f.get("brand_name", "").strip() or not f.get("generic_name", "").strip() or not to_float(f.get("mrp")):
            flash("Brand, generic name and MRP are required.", "error")
        else:
            med = med or Medicine(mrp=0)
            _fill_medicine(med, f)
            db.session.add(med)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Could not save. Is the barcode already used by another medicine?", "error")
                return render_template("admin/medicine_form.html", med=med, suppliers=Supplier.query.all())
            flash("Medicine saved.", "ok")
            return redirect(url_for("admin.medicine_detail", medicine_id=med.id))
    return render_template("admin/medicine_form.html", med=med, suppliers=Supplier.query.all())


@admin_bp.route("/inventory/<int:medicine_id>")
@admin_only
def medicine_detail(medicine_id):
    med = db.session.get(Medicine, medicine_id) or abort(404)
    batches = med.batches.order_by(Batch.expiry_date).all()
    branch_id = current_branch_id()
    return render_template("admin/medicine_detail.html", med=med, batches=batches, current_branch_id=branch_id,
                           qty=available_quantities([med.id], branch_id)[med.id], today=date.today())


@admin_bp.route("/inventory/<int:medicine_id>/delete", methods=["POST"])
@admin_only
def medicine_delete(medicine_id):
    med = db.session.get(Medicine, medicine_id) or abort(404)
    med.soft_delete()          # hidden, never physically deleted
    db.session.commit()
    flash(f"{med.brand_name} was removed from the catalogue (history is kept).", "ok")
    return redirect(url_for("admin.inventory"))


@admin_bp.route("/inventory/<int:medicine_id>/batch", methods=["POST"])
@admin_only
def add_batch(medicine_id):
    med = db.session.get(Medicine, medicine_id) or abort(404)
    f = request.form
    branch_id = current_branch_id()
    expiry, qty = to_date(f.get("expiry_date")), to_int(f.get("quantity"), 0, minimum=1)
    if not f.get("batch_no", "").strip() or not expiry or not qty:
        flash("Batch number, expiry date and quantity are required.", "error")
    elif Batch.query.filter_by(medicine_id=med.id, batch_no=f["batch_no"].strip(), branch_id=branch_id).first():
        flash("That batch number already exists at this branch. Receive extra stock through a purchase order.",
              "error")
    else:
        db.session.add(Batch(medicine_id=med.id, batch_no=f["batch_no"].strip(), expiry_date=expiry, quantity=qty,
                             branch_id=branch_id, purchase_price=to_float(f.get("purchase_price"), 0.0),
                             supplier_id=med.preferred_supplier_id))
        db.session.commit()
        from app.services.notifications import notify_restock
        notify_restock(med.id)
        flash("Batch added.", "ok")
    return redirect(url_for("admin.medicine_detail", medicine_id=med.id))


@admin_bp.route("/batch/<int:batch_id>/remove", methods=["POST"])
@admin_only
def remove_stock(batch_id):
    """Write off expired/damaged units, or send them back to the supplier."""
    batch = db.session.get(Batch, batch_id) or abort(404)
    qty = to_int(request.form.get("quantity"), 0, minimum=1)
    reason, kind = request.form.get("reason", "expired"), request.form.get("kind", "writeoff")
    if not qty or qty > batch.quantity:
        flash(f"Enter a quantity between 1 and {batch.quantity}.", "error")
    else:
        batch.quantity -= qty
        if kind == "supplier":
            db.session.add(SupplierReturn(batch_id=batch.id, supplier_id=batch.supplier_id, quantity=qty, reason=reason))
        else:
            db.session.add(StockWriteoff(batch_id=batch.id, quantity=qty, reason=reason, created_by=current_user.id,
                                         note=request.form.get("note", "")[:200]))
        db.session.commit()
        flash("Stock removed and recorded.", "ok")
    return redirect(request.referrer or url_for("admin.medicine_detail", medicine_id=batch.medicine_id))


# ---------------- reports ----------------
REPORT_TITLES = {
    "near_expiry": "Near-expiry stock (sell earliest first)", "expired": "Expired stock (remove from shelf)",
    "low_stock": "Low stock", "dead_stock": "Dead stock (no recent sales)", "abc": "ABC / VED analysis",
    "forecast": "Demand forecast (next 30 days)", "profit": "Profit by medicine (30 days)",
    "unmet": "Unmet demand from customer searches", "dues": "Supplier dues",
}


@admin_bp.route("/reports")
@admin_only
def report_view():
    view = request.args.get("view", "near_expiry")
    if view not in REPORT_TITLES:
        abort(404)
    if view == "near_expiry":
        headers = ["Medicine", "Batch", "Expires", "Days left", "Qty", "Suggestion"]
        rows = [[b.medicine.display_name, b.batch_no, f"{b.expiry_date:%d %b %Y}", b.days_left, b.quantity,
                 "Discount and sell first" if b.days_left <= 45 else "Sell first (FEFO)"] for b in reports.near_expiry()]
    elif view == "expired":
        headers = ["Medicine", "Batch", "Expired on", "Qty", "Action"]
        rows = [[b.medicine.display_name, b.batch_no, f"{b.expiry_date:%d %b %Y}", b.quantity, "Write off / return to supplier"]
                for b in reports.expired_stock()]
    elif view == "low_stock":
        headers = ["Medicine", "Available", "Reorder level", "Criticality"]
        rows = [[r["medicine"].display_name, r["available"], r["medicine"].reorder_level, r["medicine"].criticality]
                for r in reports.low_stock()]
    elif view == "dead_stock":
        headers = ["Medicine", "In stock", "Idea"]
        rows = [[r["medicine"].display_name, r["available"], "Discount, bundle or return to supplier"]
                for r in reports.dead_stock()]
    elif view == "abc":
        headers = ["Medicine", "Sales value (12 mo)", "ABC", "VED", "Note"]
        rows = [[r["medicine"].display_name, f"Rs {r['value']:,.2f}", r["abc"], r["ved"],
                 "Vital: never let this run out" if r["never_stock_out"] else ""] for r in forecasting.abc_ved_analysis()]
    elif view == "forecast":
        headers = ["Medicine", "Sold (90 days)", "Forecast (30 days)", "Available now", "Suggested order"]
        meds = Medicine.query.filter(Medicine.deleted_at.is_(None)).order_by(Medicine.brand_name).all()
        avail = available_quantities([m.id for m in meds])
        rows = []
        for m in meds:
            fc = forecasting.forecast_next_30_days(m.id)
            rows.append([m.display_name, forecasting.units_sold(m.id), fc, avail[m.id], max(fc - avail[m.id], 0)])
    elif view == "profit":
        headers = ["Medicine", "Units", "Revenue (ex-GST)", "Cost", "Profit"]
        rows = [[r["name"], r["units"], f"Rs {r['revenue']:,.2f}", f"Rs {r['cost']:,.2f}", f"Rs {r['profit']:,.2f}"]
                for r in reports.profit_by_medicine()]
    elif view == "unmet":
        headers = ["Search term", "Times searched", "Matches", "Out of stock hits"]
        rows = [[q, n, int(r or 0), int(o or 0)] for q, n, r, o in reports.unmet_demand()]
    else:
        headers = ["Supplier", "Invoice", "Due date", "Amount", "Paid", "Outstanding"]
        rows = [[g.supplier.name, g.supplier_invoice_no or "-", f"{g.due_date:%d %b %Y}", f"Rs {g.amount:,.2f}",
                 f"Rs {g.amount_paid:,.2f}", f"Rs {g.outstanding:,.2f}"] for g in reports.supplier_dues()]
    return render_template("admin/reports.html", view=view, titles=REPORT_TITLES, headers=headers, rows=rows)


@admin_bp.route("/export/sales.csv")
@admin_only
def export_sales():
    days = to_int(request.args.get("days"), 30, minimum=1)
    since = datetime.combine(date.today() - timedelta(days=days), time.min)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Invoice", "Date", "Customer", "Payment", "Subtotal", "Discount", "GST", "Total"])
    for i in Invoice.query.filter(Invoice.created_at >= since).order_by(Invoice.created_at).all():
        w.writerow([i.invoice_no, f"{i.created_at:%Y-%m-%d %H:%M}", i.customer.name if i.customer else "Walk-in",
                    i.payment_mode, i.subtotal, i.discount, i.gst_amount, i.total])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=sales_{date.today()}.csv"})


# ---------------- purchasing ----------------
@admin_bp.route("/purchase")
@admin_only
def purchase():
    pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    return render_template("admin/purchase.html", pos=pos, suggestions=purchase_automation.reorder_suggestions())


@admin_bp.route("/purchase/generate", methods=["POST"])
@admin_only
def purchase_generate():
    created = purchase_automation.generate_purchase_orders(current_user.id)
    flash(f"Created {len(created)} draft purchase order(s)." if created else
          "Nothing to order: every low-stock medicine is already on an open order.", "ok")
    return redirect(url_for("admin.purchase"))


@admin_bp.route("/purchase/<int:po_id>", methods=["GET", "POST"])
@admin_only
def purchase_detail(po_id):
    po = db.session.get(PurchaseOrder, po_id) or abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "send" and po.status == "draft":
            po.status = "sent"
            flash("Marked as sent to the supplier.", "ok")
        elif action == "cancel" and po.status in ("draft", "sent"):
            po.status = "cancelled"
            flash("Purchase order cancelled.", "ok")
        elif action == "receive" and po.status in ("draft", "sent"):
            rows = []
            for it in po.items:
                expiry = to_date(request.form.get(f"expiry_{it.id}"))
                batch_no = request.form.get(f"batch_{it.id}", "").strip()
                qty = to_int(request.form.get(f"qty_{it.id}"), it.quantity, minimum=0)
                if qty and (not expiry or not batch_no):
                    flash(f"Enter batch number and expiry for {it.medicine.brand_name}.", "error")
                    return redirect(url_for("admin.purchase_detail", po_id=po.id))
                rows.append({"item_id": it.id, "batch_no": batch_no, "expiry_date": expiry, "quantity": qty})
            purchase_automation.receive_purchase_order(po.id, current_user.id, rows,
                                                       request.form.get("supplier_invoice_no", ""),
                                                       branch_id=current_branch_id())
            flash("Goods received. Batches were added to stock and 'notify me' subscribers alerted.", "ok")
        db.session.commit()
        return redirect(url_for("admin.purchase_detail", po_id=po.id))
    return render_template("admin/purchase_detail.html", po=po)


@admin_bp.route("/suppliers", methods=["GET", "POST"])
@admin_only
def suppliers():
    if request.method == "POST" and request.form.get("name", "").strip():
        f = request.form
        db.session.add(Supplier(name=f["name"].strip(), phone=f.get("phone", ""), email=f.get("email", ""),
                                gst_no=f.get("gst_no", ""), payment_terms_days=to_int(f.get("payment_terms_days"), 30)))
        db.session.commit()
        flash("Supplier added.", "ok")
        return redirect(url_for("admin.suppliers"))
    rows = [[s.name, s.phone, s.email, s.gst_no, f"{s.payment_terms_days} days"] for s in Supplier.query.all()]
    fields = [("name", "Name", "text"), ("phone", "Phone", "text"), ("email", "Email", "email"),
              ("gst_no", "GST number", "text"), ("payment_terms_days", "Payment terms (days)", "number")]
    return _generic_page("Suppliers", ["Name", "Phone", "Email", "GST no.", "Terms"], rows, fields,
                         url_for("admin.suppliers"), button="Add supplier")


@admin_bp.route("/suppliers/pay", methods=["POST"])
@admin_only
def supplier_pay():
    g = db.session.get(GoodsReceipt, to_int(request.form.get("receipt_id"), 0)) or abort(404)
    amt = to_float(request.form.get("amount"), 0.0)
    g.amount_paid = min(g.amount, (g.amount_paid or 0) + max(amt, 0))
    db.session.commit()
    flash("Payment recorded.", "ok")
    return redirect(url_for("admin.report_view", view="dues"))


# ---------------- finance ----------------
@admin_bp.route("/expenses", methods=["GET", "POST"])
@admin_only
def expenses():
    if request.method == "POST":
        f = request.form
        amt = to_float(f.get("amount"))
        if f.get("category") and amt and amt > 0:
            db.session.add(Expense(category=f["category"], amount=amt, spent_on=to_date(f.get("spent_on"), date.today()),
                                   note=f.get("note", "")[:200]))
            db.session.commit()
            flash("Expense saved.", "ok")
        return redirect(url_for("admin.expenses"))
    since = date.today() - timedelta(days=30)
    spent = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(Expense.spent_on >= since).scalar()
    profit = sum(r["profit"] for r in reports.profit_by_medicine(30))
    rows = [[e.spent_on.strftime("%d %b %Y"), e.category, f"Rs {e.amount:,.2f}", e.note]
            for e in Expense.query.order_by(Expense.spent_on.desc()).limit(50)]
    fields = [("category", "Category (rent, salary, electricity...)", "text"), ("amount", "Amount", "number"),
              ("spent_on", "Date", "date"), ("note", "Note", "text")]
    intro = (f"Last 30 days: gross profit Rs {profit:,.2f} - expenses Rs {spent:,.2f} = "
             f"net Rs {profit - spent:,.2f}")
    return _generic_page("Expenses and net profit", ["Date", "Category", "Amount", "Note"], rows, fields,
                         url_for("admin.expenses"), intro, "Add expense")


@admin_bp.route("/offers", methods=["GET", "POST"])
@admin_only
def offers():
    if request.method == "POST":
        f = request.form
        pct = to_float(f.get("discount_percent"))
        if f.get("name") and pct and 0 < pct <= 50:
            db.session.add(Offer(name=f["name"], discount_percent=pct, category=f.get("category") or None,
                                 ends_on=to_date(f.get("ends_on"))))
            db.session.commit()
            flash("Offer created. It applies automatically at billing.", "ok")
        else:
            flash("Enter a name and a discount between 1 and 50%.", "error")
        return redirect(url_for("admin.offers"))
    rows = [[o.name, f"{o.discount_percent:g}%", o.category or "All medicines",
             o.ends_on.strftime("%d %b %Y") if o.ends_on else "No end date"] for o in Offer.query.all()]
    fields = [("name", "Offer name", "text"), ("discount_percent", "Discount %", "number"),
              ("category", "Category (blank = all)", "text"), ("ends_on", "Ends on", "date")]
    return _generic_page("Discounts and offers", ["Offer", "Discount", "Applies to", "Ends"], rows, fields,
                         url_for("admin.offers"), button="Create offer")


@admin_bp.route("/credit", methods=["GET", "POST"])
@admin_only
def credit():
    if request.method == "POST":
        cust = db.session.get(Customer, to_int(request.form.get("customer_id"), 0))
        amt = to_float(request.form.get("amount"))
        if cust and amt and amt > 0:
            db.session.add(CreditLedger(customer_id=cust.id, amount=-amt, note="Payment received"))
            db.session.commit()
            flash("Payment recorded.", "ok")
        return redirect(url_for("admin.credit"))
    bal = (db.session.query(Customer, func.sum(CreditLedger.amount)).join(CreditLedger).group_by(Customer.id).all())
    rows = [[c.id, c.name, c.phone, f"Rs {b:,.2f}"] for c, b in bal if b and b > 0.005]
    fields = [("customer_id", "Customer ID (from the list)", "number"), ("amount", "Amount received", "number")]
    return _generic_page("Customer credit ledger", ["ID", "Customer", "Phone", "Owes"], rows, fields,
                         url_for("admin.credit"), "Credit sales appear here automatically.", "Record payment")


# ---------------- compliance ----------------
@admin_bp.route("/register")
@admin_only
def register():
    end = to_date(request.args.get("end"), date.today())
    start = to_date(request.args.get("start"), end - timedelta(days=30))
    rows = scheduled_drugs.register_rows(start, end)
    return render_template("admin/register.html", rows=rows, headers=scheduled_drugs.HEADERS, start=start, end=end)


@admin_bp.route("/register.csv")
@admin_only
def register_csv():
    end = to_date(request.args.get("end"), date.today())
    start = to_date(request.args.get("start"), end - timedelta(days=30))
    return Response(scheduled_drugs.to_csv(scheduled_drugs.register_rows(start, end)), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=schedule_h1_x_register.csv"})


@admin_bp.route("/audit")
@admin_only
def audit():
    names = {u.id: u.username for u in User.query.all()}
    rows = [[f"{a.created_at:%d %b %H:%M:%S}", names.get(a.user_id, "system"), a.action, a.table_name, a.record_id,
             (a.new_values or "")[:110]] for a in AuditLog.query.order_by(AuditLog.id.desc()).limit(200)]
    return _generic_page("Audit trail (latest 200 changes)", ["When", "Who", "Action", "Table", "Record", "New values"],
                         rows)


# ---------------- branches ----------------
@admin_bp.route("/branches", methods=["GET", "POST"])
@admin_only
def branches():
    if request.method == "POST":
        f = request.form
        if not f.get("name", "").strip():
            flash("Enter a branch name.", "error")
        else:
            db.session.add(Branch(pharmacy_id=current_user.pharmacy_id or 1, name=f["name"].strip(),
                                  address=f.get("address", "").strip(), phone=f.get("phone", "").strip(),
                                  latitude=to_float(f.get("latitude")), longitude=to_float(f.get("longitude"))))
            db.session.commit()
            flash("Branch added. Switch to it from the branch selector in the top bar.", "ok")
        return redirect(url_for("admin.branches"))
    rows = pharmacy_branches()
    return render_template("admin/branches.html", rows=rows, current_branch_id=current_branch_id())


@admin_bp.route("/branches/<int:branch_id>/toggle", methods=["POST"])
@admin_only
def branch_toggle(branch_id):
    b = db.session.get(Branch, branch_id) or abort(404)
    if len([x for x in pharmacy_branches() if x.active]) <= 1 and b.active:
        flash("You need at least one active branch.", "error")
    else:
        b.active = not b.active
        db.session.commit()
        flash(f"{b.name} is now {'active' if b.active else 'inactive'}.", "ok")
    return redirect(url_for("admin.branches"))


# ---------------- staff ----------------
@admin_bp.route("/staff", methods=["GET", "POST"])
@admin_only
def staff():
    if request.method == "POST":
        f = request.form
        role = Role.query.filter_by(name=f.get("role")).first()
        if (not role or role.name == "customer" or len(f.get("username", "")) < 3 or len(f.get("password", "")) < 8
                or User.query.filter_by(username=f["username"]).first()):
            flash("Need a unique username (3+ chars), a password (8+ chars) and a staff role.", "error")
        else:
            u = User(username=f["username"].strip(), full_name=f.get("full_name", ""), role_id=role.id)
            u.set_password(f["password"])
            db.session.add(u)
            db.session.commit()
            flash("Staff account created.", "ok")
        return redirect(url_for("admin.staff"))
    since = datetime.combine(date.today() - timedelta(days=30), time.min)
    sales = dict(db.session.query(Invoice.cashier_id, func.sum(Invoice.total)).filter(Invoice.created_at >= since)
                 .group_by(Invoice.cashier_id).all())
    hours = {}
    for s in Shift.query.filter(Shift.clock_in >= since, Shift.clock_out.isnot(None)).all():
        hours[s.user_id] = hours.get(s.user_id, 0) + (s.clock_out - s.clock_in).total_seconds() / 3600
    rows = [[u.username, u.full_name, u.role_name, f"Rs {sales.get(u.id, 0) or 0:,.2f}", f"{hours.get(u.id, 0):.1f} h"]
            for u in User.query.join(Role).filter(Role.name != "customer")]
    fields = [("username", "Username", "text"), ("full_name", "Full name", "text"),
              ("password", "Password (8+ characters)", "password"), ("role", "Role (admin, pharmacist, cashier)", "text")]
    return _generic_page("Staff", ["Username", "Name", "Role", "Sales (30 days)", "Hours (30 days)"], rows, fields,
                         url_for("admin.staff"), button="Create account")
