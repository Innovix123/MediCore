import os
from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory,
                   session, url_for)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (Feedback, FamilyMember, Medicine, Order, OrderItem, PatientAllergy, PatientMedication,
                        PrescriptionUpload, Reservation, StockAlertSubscription)
from app.models.base import utcnow
from app.services.availability import alternatives_for, available_quantity, stock_status
from app.utils.decorators import role_required
from app.utils.security import unique_filename
from app.utils.validators import allowed_file, to_date, to_int

customer_bp = Blueprint("customer", __name__)
customer_only = role_required("customer")


def _me():
    return current_user.customer


@customer_bp.route("/")
def home():
    """The very first thing anyone sees is the login/create-account page. Once logged in,
    each role lands on the page that makes sense for them."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.role_name == "admin":
        return redirect(url_for("admin.dashboard"))
    if current_user.role_name in ("pharmacist", "cashier"):
        return redirect(url_for("pharmacist.pos"))
    return render_template("customer/search.html")



@customer_bp.route("/medicine/<int:medicine_id>")
def medicine(medicine_id):
    med = db.session.get(Medicine, medicine_id)
    if not med or med.deleted_at:
        abort(404)
    qty = available_quantity(med.id)
    status = stock_status(qty, med.reorder_level)
    return render_template("customer/medicine.html", med=med, status=status,
                           alternatives=alternatives_for(med) if status != "in_stock" else [])


@customer_bp.route("/notify", methods=["POST"])
def notify():
    med = db.session.get(Medicine, to_int(request.form.get("medicine_id"), 0))
    contact = request.form.get("contact", "").strip()
    if not med or len(contact) < 5:
        flash("Enter a valid phone number or email.", "error")
    else:
        db.session.add(StockAlertSubscription(medicine_id=med.id, contact=contact))
        db.session.commit()
        flash(f"We'll tell you when {med.brand_name} is back in stock.", "ok")
    return redirect(request.referrer or url_for("customer.home"))


@customer_bp.route("/reserve", methods=["POST"])
@customer_only
def reserve():
    med = db.session.get(Medicine, to_int(request.form.get("medicine_id"), 0))
    qty = to_int(request.form.get("quantity"), 1, minimum=1)
    if not med:
        abort(404)
    if med.needs_rx:
        flash("Prescription medicines can't be reserved online. Upload a prescription and place an order.", "error")
    elif available_quantity(med.id) < qty:
        flash("Not enough stock to reserve that quantity.", "error")
    else:
        hours = current_app.config["RESERVATION_HOURS"]
        db.session.add(Reservation(medicine_id=med.id, customer_id=_me().id, quantity=qty,
                                   expires_at=utcnow() + timedelta(hours=hours)))
        db.session.commit()
        flash(f"Reserved {qty} x {med.brand_name} for {hours} hours. Collect it at the store.", "ok")
    return redirect(url_for("customer.medicine", medicine_id=med.id))


# ---------------- cart & orders ----------------
def _cart():
    return session.setdefault("cart", {})


@customer_bp.route("/cart")
def cart():
    items, total = [], 0.0
    for mid, qty in _cart().items():
        med = db.session.get(Medicine, int(mid))
        if med and not med.deleted_at:
            items.append({"med": med, "qty": qty, "line": round(med.mrp * qty, 2)})
            total += med.mrp * qty
    uploads = []
    if current_user.is_authenticated and current_user.role_name == "customer":
        uploads = PrescriptionUpload.query.filter(PrescriptionUpload.customer_id == _me().id,
                                                  PrescriptionUpload.status != "rejected").all()
    return render_template("customer/cart.html", items=items, total=round(total, 2), uploads=uploads,
                           needs_rx=any(i["med"].needs_rx for i in items))


@customer_bp.route("/cart/add", methods=["POST"])
def cart_add():
    med = db.session.get(Medicine, to_int(request.form.get("medicine_id"), 0))
    qty = to_int(request.form.get("quantity"), 1, minimum=1)
    if not med:
        abort(404)
    cart_ = _cart()
    cart_[str(med.id)] = cart_.get(str(med.id), 0) + qty
    session.modified = True
    flash(f"Added {med.brand_name} to your cart.", "ok")
    return redirect(request.referrer or url_for("customer.cart"))


@customer_bp.route("/cart/remove/<int:medicine_id>", methods=["POST"])
def cart_remove(medicine_id):
    _cart().pop(str(medicine_id), None)
    session.modified = True
    return redirect(url_for("customer.cart"))


@customer_bp.route("/checkout", methods=["POST"])
@customer_only
def checkout():
    cart_ = _cart()
    if not cart_:
        flash("Your cart is empty.", "error")
        return redirect(url_for("customer.cart"))
    fulfilment = "delivery" if request.form.get("fulfilment") == "delivery" else "pickup"
    address = request.form.get("address", "").strip() or _me().address
    if fulfilment == "delivery" and not address:
        flash("Enter a delivery address.", "error")
        return redirect(url_for("customer.cart"))

    meds = {int(k): db.session.get(Medicine, int(k)) for k in cart_}
    for mid, qty in cart_.items():
        if available_quantity(int(mid)) < qty:
            flash(f"Sorry, {meds[int(mid)].brand_name} doesn't have {qty} units available right now.", "error")
            return redirect(url_for("customer.cart"))

    status, upload = "placed", None
    if any(m.needs_rx for m in meds.values()):
        upload = db.session.get(PrescriptionUpload, to_int(request.form.get("upload_id"), 0))
        if not upload or upload.customer_id != _me().id or upload.status == "rejected":
            flash("Your cart has prescription medicines. Upload a prescription and select it.", "error")
            return redirect(url_for("customer.cart"))
        status = "placed" if upload.status == "approved" else "awaiting_prescription"

    order = Order(customer_id=_me().id, status=status, fulfilment=fulfilment, address=address,
                  prescription_upload_id=upload.id if upload else None)
    total = 0.0
    for mid, qty in cart_.items():
        med = meds[int(mid)]
        order.items.append(OrderItem(medicine_id=med.id, quantity=qty, unit_price=med.mrp))
        total += med.mrp * qty
    order.total = round(total, 2)
    db.session.add(order)
    db.session.commit()
    session.pop("cart", None)
    flash("Order placed." if status == "placed" else "Order placed. It will be processed once a pharmacist "
          "verifies your prescription.", "ok")
    return redirect(url_for("customer.order_detail", order_id=order.id))


@customer_bp.route("/orders")
@customer_only
def orders():
    rows = Order.query.filter_by(customer_id=_me().id).order_by(Order.created_at.desc()).all()
    return render_template("customer/orders.html", orders=rows)


@customer_bp.route("/orders/<int:order_id>")
@customer_only
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.customer_id != _me().id:
        abort(404)
    steps = ["placed", "packed", "out_for_delivery" if order.fulfilment == "delivery" else "ready_for_pickup", "delivered"]
    return render_template("customer/order_detail.html", order=order, steps=steps)


@customer_bp.route("/orders/<int:order_id>/reorder", methods=["POST"])
@customer_only
def reorder(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.customer_id != _me().id:
        abort(404)
    for it in order.items:
        _cart()[str(it.medicine_id)] = it.quantity
    session.modified = True
    flash("Items from that order are back in your cart.", "ok")
    return redirect(url_for("customer.cart"))


@customer_bp.route("/orders/<int:order_id>/feedback", methods=["POST"])
@customer_only
def feedback(order_id):
    order = db.session.get(Order, order_id)
    rating = to_int(request.form.get("rating"), 0)
    if not order or order.customer_id != _me().id or rating not in range(1, 6):
        abort(400)
    db.session.add(Feedback(customer_id=_me().id, order_id=order.id, rating=rating,
                            comment=request.form.get("comment", "")[:400]))
    db.session.commit()
    flash("Thanks for your feedback.", "ok")
    return redirect(url_for("customer.order_detail", order_id=order.id))


# ---------------- prescriptions ----------------
@customer_bp.route("/prescriptions", methods=["GET", "POST"])
@customer_only
def prescriptions():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename or not allowed_file(f.filename, current_app.config["ALLOWED_UPLOADS"]):
            flash("Choose a JPG, PNG or PDF file (max 5 MB).", "error")
        else:
            name = unique_filename(f.filename)
            f.save(os.path.join(current_app.config["UPLOAD_FOLDER"], name))
            db.session.add(PrescriptionUpload(customer_id=_me().id, file_path=name, original_name=f.filename[:200],
                                              doctor_name=request.form.get("doctor_name", "").strip()[:120]))
            db.session.commit()
            flash("Prescription uploaded. A pharmacist will review it shortly.", "ok")
        return redirect(url_for("customer.prescriptions"))
    rows = (PrescriptionUpload.query.filter_by(customer_id=_me().id)
            .order_by(PrescriptionUpload.uploaded_at.desc()).all())
    return render_template("customer/prescriptions.html", uploads=rows)


@customer_bp.route("/files/prescription/<int:upload_id>")
@login_required
def prescription_file(upload_id):
    up = db.session.get(PrescriptionUpload, upload_id)
    if not up:
        abort(404)
    owner = current_user.role_name == "customer" and current_user.customer and up.customer_id == current_user.customer.id
    if not (owner or current_user.role_name in ("admin", "pharmacist")):
        abort(403)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], up.file_path)


# ---------------- profile: family, allergies, regular medicines ----------------
@customer_bp.route("/profile", methods=["GET", "POST"])
@customer_only
def profile():
    me = _me()
    if request.method == "POST":
        kind, f = request.form.get("form_type"), request.form
        if kind == "family" and f.get("name", "").strip():
            db.session.add(FamilyMember(customer_id=me.id, name=f["name"].strip(), relation=f.get("relation", "")))
        elif kind == "allergy" and f.get("allergen", "").strip():
            db.session.add(PatientAllergy(customer_id=me.id, allergen=f["allergen"].strip(),
                                          family_member_id=to_int(f.get("family_member_id")) or None))
        elif kind == "medication":
            med = db.session.get(Medicine, to_int(f.get("medicine_id"), 0))
            if med:
                db.session.add(PatientMedication(customer_id=me.id, medicine_id=med.id, dosage=f.get("dosage", ""),
                                                 days_supply=to_int(f.get("days_supply"), 30, minimum=1),
                                                 last_refill_on=to_date(f.get("last_refill_on"))))
        elif kind == "details":
            me.name, me.phone = f.get("name", me.name).strip(), f.get("phone", "").strip()
            me.address = f.get("address", "").strip()
        db.session.commit()
        flash("Saved.", "ok")
        return redirect(url_for("customer.profile"))
    meds = Medicine.query.filter(Medicine.deleted_at.is_(None)).order_by(Medicine.brand_name).all()
    return render_template("customer/profile.html", me=me, all_meds=meds)


@customer_bp.route("/profile/delete/<kind>/<int:item_id>", methods=["POST"])
@customer_only
def profile_delete(kind, item_id):
    model = {"family": FamilyMember, "allergy": PatientAllergy, "medication": PatientMedication}.get(kind)
    obj = db.session.get(model, item_id) if model else None
    if not obj or obj.customer_id != _me().id:
        abort(404)
    db.session.delete(obj)
    db.session.commit()
    return redirect(url_for("customer.profile"))
