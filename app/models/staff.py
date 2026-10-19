from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager
from app.models.base import TimestampMixin, utcnow

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)  # admin/pharmacist/cashier/customer
    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles")


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.String(200), default="")


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    full_name = db.Column(db.String(120), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacies.id"), nullable=True, index=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    pharmacy = db.relationship("Pharmacy")

    role = db.relationship("Role")
    customer = db.relationship("Customer", uselist=False, backref="user")

    @property
    def is_active(self):  # Flask-Login hook
        return self.active

    @property
    def role_name(self):
        return self.role.name if self.role else ""

    @property
    def is_staff(self):
        return self.role_name in ("admin", "pharmacist", "cashier")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def can(self, code):
        return any(p.code == code for p in self.role.permissions)


class Shift(db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    clock_in = db.Column(db.DateTime, default=utcnow, nullable=False)
    clock_out = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
