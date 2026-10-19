from app.extensions import db
from app.models.base import utcnow


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    registration_no = db.Column(db.String(40), default="")
    phone = db.Column(db.String(20), default="")


class Prescription(db.Model):
    """A verified prescription that a sale can be linked to."""
    __tablename__ = "prescriptions"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("prescription_uploads.id"), nullable=True)
    issued_on = db.Column(db.Date, nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=utcnow)

    doctor = db.relationship("Doctor")
    customer = db.relationship("Customer")


class PrescriptionUpload(db.Model):
    __tablename__ = "prescription_uploads"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(200), default="")
    doctor_name = db.Column(db.String(120), default="")
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending/approved/rejected
    reject_reason = db.Column(db.String(200), default="")
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=utcnow)

    customer = db.relationship("Customer")
    reviewer = db.relationship("User")


class DrugInteraction(db.Model):
    __tablename__ = "drug_interactions"

    id = db.Column(db.Integer, primary_key=True)
    drug_a = db.Column(db.String(80), nullable=False, index=True)   # ingredient names, lowercase
    drug_b = db.Column(db.String(80), nullable=False, index=True)
    severity = db.Column(db.String(10), default="moderate")         # minor/moderate/major
    note = db.Column(db.String(255), default="")


class CounselingNote(db.Model):
    __tablename__ = "counseling_notes"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    pharmacist_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    pharmacist = db.relationship("User")
