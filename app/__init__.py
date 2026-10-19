from datetime import datetime

from flask import Flask, render_template, session
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from markupsafe import Markup

from app.extensions import csrf, db, limiter, login_manager, migrate
from config import Config


def create_app(config_object=Config):
    import os
    app = Flask(__name__)
    app.config.from_object(config_object)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    from app import models  # noqa: F401  (registers tables + audit listeners)
    from app.routes.admin_routes import admin_bp
    from app.routes.api_routes import api_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.customer_routes import customer_bp
    from app.routes.pharmacist_routes import pharmacist_bp
    for bp in (customer_bp, auth_bp, pharmacist_bp, admin_bp, api_bp):
        app.register_blueprint(bp)

    from app.utils.i18n import current_lang, t
    app.jinja_env.globals.update(
        t=t, now=datetime.now, lang=current_lang,
        csrf_field=lambda: Markup(f'<input type="hidden" name="csrf_token" value="{generate_csrf()}">'))
    app.jinja_env.filters["money"] = lambda v: f"Rs {float(v or 0):,.2f}"

    @app.context_processor
    def inject_branch_switcher():
        """Makes the branch selector available in base.html for any staff member, on every page,
        without every single route having to fetch and pass it in."""
        if not (current_user.is_authenticated and current_user.role_name in ("admin", "pharmacist", "cashier")):
            return {}
        from app.models import Branch
        q = Branch.query.filter_by(active=True)
        if current_user.pharmacy_id:
            q = q.filter_by(pharmacy_id=current_user.pharmacy_id)
        branches = q.order_by(Branch.name).all()
        current_id = session.get("branch_id") or (branches[0].id if branches else 1)
        return {"nav_branches": branches, "nav_current_branch_id": current_id}

    for code, title, msg in ((403, "Not allowed", "Your account does not have access to this page."),
                             (404, "Page not found", "That page does not exist."),
                             (413, "File too large", "Uploads can be at most 5 MB.")):
        app.register_error_handler(code, lambda e, c=code, ti=title, m=msg: (
            render_template("error.html", code=c, title=ti, message=m), c))

    from app.cli import register_cli
    register_cli(app)

    if not app.config.get("TESTING"):
        from app.scheduler import start_scheduler
        start_scheduler(app)

    return app
