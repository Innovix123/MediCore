from datetime import date, timedelta

from app.extensions import db
from app.models import Batch, Customer, Reservation
from app.models.base import utcnow
from app.services.availability import (available_quantity, find_medicines, stock_status)


def test_expired_batches_are_not_available(app, medicine):
    db.session.add(Batch(medicine_id=medicine.id, batch_no="OLD", expiry_date=date.today() - timedelta(days=1),
                         quantity=999))
    db.session.commit()
    assert available_quantity(medicine.id) == 50


def test_active_reservation_reduces_availability(app, medicine):
    cust = Customer(name="Test", phone="1")
    db.session.add(cust)
    db.session.flush()
    db.session.add(Reservation(medicine_id=medicine.id, customer_id=cust.id, quantity=10, status="active",
                               expires_at=utcnow() + timedelta(hours=1)))
    db.session.commit()
    assert available_quantity(medicine.id) == 40


def test_expired_reservation_does_not_reduce_availability(app, medicine):
    cust = Customer(name="Test", phone="1")
    db.session.add(cust)
    db.session.flush()
    db.session.add(Reservation(medicine_id=medicine.id, customer_id=cust.id, quantity=10, status="active",
                               expires_at=utcnow() - timedelta(hours=1)))
    db.session.commit()
    assert available_quantity(medicine.id) == 50


def test_stock_status_thresholds(app, medicine):
    assert stock_status(0, 10) == "out"
    assert stock_status(5, 10) == "low"
    assert stock_status(11, 10) == "in_stock"


def test_find_medicines_matches_generic_and_typo(app, medicine):
    assert medicine in find_medicines("paracetamol")
    assert medicine in find_medicines("dol")
    assert medicine in find_medicines("paracetmol")   # fuzzy match for a typo
