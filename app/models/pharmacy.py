"""A Pharmacy is a tenant: one independent pharmacy business on the platform.
Each pharmacy has its own branches, staff, suppliers, purchase orders, expenses and offers.
The medicine CATALOG (app.models.medicine.Medicine) is shared across all pharmacies on purpose:
it's what lets a customer search once and see which of several different pharmacies has the
medicine in stock, and whether a different brand of the same composition is available instead.
"""
from app.extensions import db
from app.models.base import TimestampMixin


class Pharmacy(TimestampMixin, db.Model):
    __tablename__ = "pharmacies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    phone = db.Column(db.String(20), default="")
    email = db.Column(db.String(120), default="")
    license_no = db.Column(db.String(60), default="")      # drug license / registration number
    active = db.Column(db.Boolean, default=True, nullable=False)

    branches = db.relationship("Branch", backref="pharmacy", cascade="all, delete-orphan")

    @property
    def main_branch(self):
        return next((b for b in self.branches if b.active), self.branches[0] if self.branches else None)
