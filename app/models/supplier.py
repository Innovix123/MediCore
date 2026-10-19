from datetime import date

from app.extensions import db
from app.models.base import Money, TimestampMixin, utcnow


class Supplier(TimestampMixin, db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacies.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default="")
    email = db.Column(db.String(120), default="")
    address = db.Column(db.String(255), default="")
    gst_no = db.Column(db.String(20), default="")
    payment_terms_days = db.Column(db.Integer, default=30)


class PurchaseOrder(TimestampMixin, db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacies.id"), nullable=False, index=True)
    po_number = db.Column(db.String(30), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)  # draft/sent/received/cancelled
    auto_generated = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    expected_on = db.Column(db.Date, nullable=True)

    supplier = db.relationship("Supplier")
    items = db.relationship("PurchaseOrderItem", backref="po", cascade="all, delete-orphan")

    @property
    def total(self):
        return round(sum(i.quantity * i.unit_cost for i in self.items), 2)


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(Money, default=0)

    medicine = db.relationship("Medicine")


class GoodsReceipt(db.Model):
    __tablename__ = "goods_receipts"

    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    supplier_invoice_no = db.Column(db.String(40), default="")
    received_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    received_at = db.Column(db.DateTime, default=utcnow)
    amount = db.Column(Money, default=0)
    amount_paid = db.Column(Money, default=0)
    due_date = db.Column(db.Date, default=date.today)

    po = db.relationship("PurchaseOrder")
    supplier = db.relationship("Supplier")

    @property
    def outstanding(self):
        return round((self.amount or 0) - (self.amount_paid or 0), 2)
