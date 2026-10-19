from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Batch, Medicine, Role, User
from app.services import billing


@pytest.fixture()
def cashier(app):
    role = Role.query.filter_by(name="cashier").first()
    u = User(username="cash1", role_id=role.id, password_hash=generate_password_hash("x"))
    db.session.add(u)
    db.session.commit()
    return u


def test_create_invoice_deducts_stock_fefo(app, medicine, cashier):
    near = Batch(medicine_id=medicine.id, batch_no="NEAR", expiry_date=date.today() + timedelta(days=5), quantity=5)
    db.session.add(near)
    db.session.commit()
    inv = billing.create_invoice(cashier.id, [{"medicine_id": medicine.id, "quantity": 3}])
    assert inv.total == pytest.approx(96.0)
    db.session.refresh(near)
    assert near.quantity == 2          # the soon-to-expire batch was used first


def test_insufficient_stock_raises(app, medicine, cashier):
    with pytest.raises(billing.BillingError):
        billing.create_invoice(cashier.id, [{"medicine_id": medicine.id, "quantity": 999}])


def test_rx_medicine_requires_prescription(app, cashier):
    rx_med = Medicine(brand_name="Azithral 500", generic_name="Azithromycin", composition="Azithromycin 500mg",
                      mrp=118, gst_percent=12, reorder_level=5, schedule="H", requires_prescription=True)
    db.session.add(rx_med)
    db.session.flush()
    db.session.add(Batch(medicine_id=rx_med.id, batch_no="A1", expiry_date=date.today() + timedelta(days=100), quantity=10))
    db.session.commit()
    with pytest.raises(billing.BillingError):
        billing.create_invoice(cashier.id, [{"medicine_id": rx_med.id, "quantity": 1}])


def test_expired_batch_is_never_sold(app, cashier):
    med = Medicine(brand_name="Crocin", generic_name="Paracetamol", composition="Paracetamol 500mg",
                   mrp=20, gst_percent=12, reorder_level=5)
    db.session.add(med)
    db.session.flush()
    db.session.add(Batch(medicine_id=med.id, batch_no="OLD", expiry_date=date.today() - timedelta(days=1), quantity=50))
    db.session.commit()
    with pytest.raises(billing.BillingError):
        billing.create_invoice(cashier.id, [{"medicine_id": med.id, "quantity": 1}])


def test_return_restocks_and_refunds(app, medicine, cashier):
    inv = billing.create_invoice(cashier.id, [{"medicine_id": medicine.id, "quantity": 2}])
    item = inv.items[0]
    before = item.batch.quantity
    ret = billing.process_return(item.id, 1, "Not needed", cashier.id)
    db.session.refresh(item)
    assert item.batch.quantity == before + 1
    assert ret.refund_amount == pytest.approx(item.line_total / item.quantity)
