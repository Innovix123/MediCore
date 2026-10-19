from app.extensions import db
from app.models.base import utcnow


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacies.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(255), default="")
    phone = db.Column(db.String(20), default="")
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None


class StockWriteoff(db.Model):
    __tablename__ = "stock_writeoffs"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(20), nullable=False)      # expired / damaged / other
    note = db.Column(db.String(200), default="")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    batch = db.relationship("Batch")


class SupplierReturn(db.Model):
    __tablename__ = "supplier_returns"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200), default="")
    status = db.Column(db.String(20), default="sent")
    created_at = db.Column(db.DateTime, default=utcnow)

    batch = db.relationship("Batch")


class StockTransfer(db.Model):
    __tablename__ = "stock_transfers"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    from_branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    to_branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
