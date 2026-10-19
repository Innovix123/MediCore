from app.extensions import db
from app.models.base import utcnow


class SearchLog(db.Model):
    """Every public search. Zero-result and out-of-stock searches show unmet demand."""
    __tablename__ = "search_logs"

    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(120), nullable=False, index=True)
    results_count = db.Column(db.Integer, default=0)
    out_of_stock_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(400), default="")
    created_at = db.Column(db.DateTime, default=utcnow)


class Reminder(db.Model):
    __tablename__ = "reminders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    patient_medication_id = db.Column(db.Integer, db.ForeignKey("patient_medications.id"), nullable=True)
    remind_on = db.Column(db.Date, nullable=False)
    channel = db.Column(db.String(10), default="sms")
    message = db.Column(db.String(255), nullable=False)
    sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)

    customer = db.relationship("Customer")


class StockAlertSubscription(db.Model):
    """'Notify me when back in stock'."""
    __tablename__ = "stock_alert_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    contact = db.Column(db.String(120), nullable=False)      # phone or email
    notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    medicine = db.relationship("Medicine")
