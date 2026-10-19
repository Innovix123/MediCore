from app.extensions import db
from app.models.base import SoftDeleteMixin, TimestampMixin


class Customer(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), index=True, default="")
    email = db.Column(db.String(120), default="")
    address = db.Column(db.String(255), default="")

    family = db.relationship("FamilyMember", backref="customer", cascade="all, delete-orphan")
    allergies = db.relationship("PatientAllergy", backref="customer", cascade="all, delete-orphan")
    medications = db.relationship("PatientMedication", backref="customer", cascade="all, delete-orphan")


class FamilyMember(db.Model):
    __tablename__ = "family_members"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    relation = db.Column(db.String(40), default="")
    dob = db.Column(db.Date, nullable=True)


class PatientAllergy(db.Model):
    __tablename__ = "patient_allergies"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    family_member_id = db.Column(db.Integer, db.ForeignKey("family_members.id"), nullable=True)
    allergen = db.Column(db.String(80), nullable=False)
    note = db.Column(db.String(200), default="")


class PatientMedication(db.Model):
    """A regular medicine a customer takes; drives refill reminders."""
    __tablename__ = "patient_medications"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    family_member_id = db.Column(db.Integer, db.ForeignKey("family_members.id"), nullable=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    dosage = db.Column(db.String(80), default="")
    days_supply = db.Column(db.Integer, default=30)
    last_refill_on = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)

    medicine = db.relationship("Medicine")
