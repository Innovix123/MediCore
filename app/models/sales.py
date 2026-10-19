from app.extensions import db
from app.models.base import Money, utcnow


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(30), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id"), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), default=1)
    subtotal = db.Column(Money, default=0)        # MRP total before discounts
    discount = db.Column(Money, default=0)
    gst_amount = db.Column(Money, default=0)      # GST contained in the total (MRP is GST-inclusive)
    total = db.Column(Money, default=0)
    payment_mode = db.Column(db.String(20), default="cash")
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    items = db.relationship("InvoiceItem", backref="invoice", cascade="all, delete-orphan")
    customer = db.relationship("Customer")
    cashier = db.relationship("User")
    prescription = db.relationship("Prescription")
    payments = db.relationship("Payment", backref="invoice")


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(Money, nullable=False)
    discount_amount = db.Column(Money, default=0)
    gst_percent = db.Column(db.Float, default=0)
    gst_amount = db.Column(Money, default=0)
    line_total = db.Column(Money, nullable=False)     # net payable for this line
    returned_qty = db.Column(db.Integer, default=0)

    medicine = db.relationship("Medicine")
    batch = db.relationship("Batch")

    @property
    def returnable(self):
        return self.quantity - (self.returned_qty or 0)


class SaleReturn(db.Model):
    __tablename__ = "sale_returns"

    id = db.Column(db.Integer, primary_key=True)
    invoice_item_id = db.Column(db.Integer, db.ForeignKey("invoice_items.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200), default="")
    refund_amount = db.Column(Money, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    item = db.relationship("InvoiceItem")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    mode = db.Column(db.String(20), default="cash")     # cash, upi, card, credit
    amount = db.Column(Money, nullable=False)
    reference = db.Column(db.String(60), default="")
    created_at = db.Column(db.DateTime, default=utcnow)
