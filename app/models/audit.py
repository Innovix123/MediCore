"""Audit trail: who changed what, when, old value -> new value.

Listeners on the SQLAlchemy session record every insert/update/delete
of the models listed in AUDITED. Nothing in the application code has to
remember to write a log entry.
"""
import json

from flask import has_request_context
from flask_login import current_user
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.base import utcnow
from app.models.medicine import Batch, Medicine
from app.models.order import Order
from app.models.prescription import PrescriptionUpload
from app.models.sales import Invoice
from app.models.supplier import PurchaseOrder, Supplier


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(60), nullable=False, index=True)
    record_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(10), nullable=False)          # insert/update/delete
    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)
    user_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)


class ConsentRecord(db.Model):
    __tablename__ = "consent_records"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    purpose = db.Column(db.String(80), nullable=False)
    granted = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


AUDITED = (Medicine, Batch, Invoice, Order, PrescriptionUpload, Supplier, PurchaseOrder)
_SKIP = {"updated_at", "created_at"}


def _user_id():
    try:
        if has_request_context() and current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None


def _snapshot(obj):
    return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs if c.key not in _SKIP}


def _changes(obj):
    old, new = {}, {}
    state = inspect(obj)
    for attr in state.mapper.column_attrs:
        if attr.key in _SKIP:
            continue
        hist = state.attrs[attr.key].history
        if hist.has_changes():
            old[attr.key] = hist.deleted[0] if hist.deleted else None
            new[attr.key] = hist.added[0] if hist.added else None
    return old, new


def _dump(d):
    return json.dumps(d, default=str) if d is not None else None


@event.listens_for(Session, "before_flush")
def _collect(session, flush_context, instances):
    pending = session.info.setdefault("audit_pending", [])
    for obj in session.new:
        if isinstance(obj, AUDITED):
            pending.append(("insert", obj, None, None))
    for obj in session.dirty:
        if isinstance(obj, AUDITED) and session.is_modified(obj, include_collections=False):
            old, new = _changes(obj)
            if new:
                pending.append(("update", obj, old, new))
    for obj in session.deleted:
        if isinstance(obj, AUDITED):
            pending.append(("delete", obj, _snapshot(obj), None))


@event.listens_for(Session, "after_flush_postexec")
def _write(session, flush_context):
    pending = session.info.pop("audit_pending", [])
    uid = _user_id()
    for action, obj, old, new in pending:
        if action == "insert":
            new = _snapshot(obj)
        session.add(AuditLog(
            table_name=obj.__tablename__, record_id=getattr(obj, "id", None), action=action,
            old_values=_dump(old), new_values=_dump(new), user_id=uid,
        ))
