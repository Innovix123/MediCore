from datetime import date

from app.extensions import db
from app.models.base import Money, utcnow


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40), nullable=False)    # rent, salary, electricity, other
    amount = db.Column(Money, nullable=False)
    spent_on = db.Column(db.Date, default=date.today, nullable=False)
    note = db.Column(db.String(200), default="")


class CreditLedger(db.Model):
    """Positive amount = credit sale (customer owes). Negative = payment received."""
    __tablename__ = "credit_ledger"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=True)
    amount = db.Column(Money, nullable=False)
    note = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=utcnow)

    customer = db.relationship("Customer")


class Offer(db.Model):
    __tablename__ = "offers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    discount_percent = db.Column(db.Float, nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=True)  # null = category/all
    category = db.Column(db.String(60), nullable=True)
    starts_on = db.Column(db.Date, default=date.today)
    ends_on = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)

    medicine = db.relationship("Medicine")


class LoyaltyPoint(db.Model):
    __tablename__ = "loyalty_points"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=utcnow)
