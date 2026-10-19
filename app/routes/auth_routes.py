from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.extensions import db, limiter
from app.models import ConsentRecord, Customer, Role, User
from app.utils.security import is_safe_next

auth_bp = Blueprint("auth", __name__)


def _home_for(user):
    if user.role_name == "admin":
        return url_for("admin.dashboard")
    if user.role_name in ("pharmacist", "cashier"):
        return url_for("pharmacist.pos")
    return url_for("customer.home")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_home_for(current_user))
    if request.method == "POST":
        ident = request.form.get("username", "").strip()
        user = User.query.filter((User.username == ident) | (User.email == ident.lower())).first()
        if user and user.active and user.check_password(request.form.get("password", "")):
            login_user(user)
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_next(nxt) else _home_for(user))
        flash("Wrong username or password.", "error")
    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("customer.home"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        username, password = f.get("username", "").strip(), f.get("password", "")
        errors = []
        if len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not f.get("name", "").strip():
            errors.append("Enter your name.")
        if not f.get("consent"):
            errors.append("Please agree to how we store your health-related data.")
        if User.query.filter_by(username=username).first():
            errors.append("That username is taken.")
        if f.get("email") and User.query.filter_by(email=f["email"].lower()).first():
            errors.append("That email is already registered.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html", form=f)
        user = User(username=username, full_name=f["name"].strip(), email=(f.get("email") or None) and f["email"].lower(),
                    role_id=Role.query.filter_by(name="customer").first().id)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        cust = Customer(user_id=user.id, name=f["name"].strip(), phone=f.get("phone", "").strip(),
                        email=f.get("email", "").strip(), address=f.get("address", "").strip())
        db.session.add(cust)
        db.session.flush()
        db.session.add(ConsentRecord(customer_id=cust.id, purpose="Store and process health-related data for orders"))
        db.session.commit()
        login_user(user)
        flash("Welcome to MediCore!", "ok")
        return redirect(url_for("customer.home"))
    return render_template("auth/register.html", form={})
