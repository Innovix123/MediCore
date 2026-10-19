from datetime import date

from app.extensions import db
from app.models.base import Money, SoftDeleteMixin, TimestampMixin


class Medicine(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)
    brand_name = db.Column(db.String(120), nullable=False, index=True)
    generic_name = db.Column(db.String(160), nullable=False, index=True)
    composition = db.Column(db.String(255), nullable=False, index=True)
    strength = db.Column(db.String(60), default="")
    form = db.Column(db.String(40), default="Tablet")
    category = db.Column(db.String(60), default="General")
    schedule = db.Column(db.String(10), default="OTC")        # OTC, H, H1, X
    requires_prescription = db.Column(db.Boolean, default=False, nullable=False)
    mrp = db.Column(Money, nullable=False)
    gst_percent = db.Column(db.Float, default=12.0, nullable=False)
    reorder_level = db.Column(db.Integer, default=20, nullable=False)
    criticality = db.Column(db.String(1), default="D", nullable=False)  # V/E/D
    barcode = db.Column(db.String(40), unique=True, nullable=True)
    preferred_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    description = db.Column(db.Text, default="")
    uses = db.Column(db.Text, default="")
    side_effects = db.Column(db.Text, default="")
    storage = db.Column(db.String(200), default="Store below 25 C, away from moisture.")

    batches = db.relationship("Batch", backref="medicine", lazy="dynamic")
    preferred_supplier = db.relationship("Supplier", foreign_keys=[preferred_supplier_id])

    @property
    def display_name(self):
        return f"{self.brand_name} {self.strength}".strip()

    @property
    def needs_rx(self):
        return self.requires_prescription or self.schedule in ("H", "H1", "X")

    def __repr__(self):
        return f"<Medicine {self.brand_name}>"


class Batch(TimestampMixin, db.Model):
    __tablename__ = "batches"
    __table_args__ = (
        db.UniqueConstraint("medicine_id", "batch_no", "branch_id", name="uq_batch"),
        db.CheckConstraint("quantity >= 0", name="ck_batch_qty_nonneg"),
    )

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), default=1, nullable=False)
    batch_no = db.Column(db.String(60), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False, index=True)
    quantity = db.Column(db.Integer, default=0, nullable=False)
    purchase_price = db.Column(Money, default=0)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    received_on = db.Column(db.Date, default=date.today)

    supplier = db.relationship("Supplier", foreign_keys=[supplier_id])
    branch = db.relationship("Branch")

    @property
    def is_expired(self):
        return self.expiry_date <= date.today()

    @property
    def days_left(self):
        return (self.expiry_date - date.today()).days
