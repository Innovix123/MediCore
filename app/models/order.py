from app.extensions import db
from app.models.base import Money, TimestampMixin, utcnow

ORDER_STATUSES = ["awaiting_prescription", "placed", "packed", "out_for_delivery",
                  "ready_for_pickup", "delivered", "cancelled"]


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    status = db.Column(db.String(30), default="placed", nullable=False)
    fulfilment = db.Column(db.String(10), default="pickup")      # pickup / delivery
    address = db.Column(db.String(255), default="")
    prescription_upload_id = db.Column(db.Integer, db.ForeignKey("prescription_uploads.id"), nullable=True)
    total = db.Column(Money, default=0)

    customer = db.relationship("Customer")
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    delivery = db.relationship("Delivery", backref="order", uselist=False)
    prescription_upload = db.relationship("PrescriptionUpload")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(Money, nullable=False)

    medicine = db.relationship("Medicine")


class Delivery(db.Model):
    __tablename__ = "deliveries"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, unique=True)
    driver_name = db.Column(db.String(80), default="")
    driver_phone = db.Column(db.String(20), default="")
    status = db.Column(db.String(20), default="assigned")
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class Reservation(db.Model):
    """Hold stock for pickup. Active reservations reduce displayed availability."""
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), default=1, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(12), default="active", nullable=False)  # active/fulfilled/expired/cancelled
    created_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    medicine = db.relationship("Medicine")
    customer = db.relationship("Customer")
