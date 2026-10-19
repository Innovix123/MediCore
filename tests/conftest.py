from datetime import date, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Batch, Customer, Medicine, Permission, Role, User


@pytest.fixture()
def app():
    from config import TestConfig
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        for name in ("admin", "pharmacist", "cashier", "customer"):
            db.session.add(Role(name=name))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def medicine(app):
    m = Medicine(brand_name="Dolo 650", generic_name="Paracetamol", composition="Paracetamol 650mg",
                strength="650 mg", mrp=32, gst_percent=12, reorder_level=10)
    db.session.add(m)
    db.session.flush()
    db.session.add(Batch(medicine_id=m.id, batch_no="B1", expiry_date=date.today() + timedelta(days=200), quantity=50))
    db.session.commit()
    return m


@pytest.fixture()
def logged_in_customer(app, client):
    """Creates a customer user, logs the test client in, and returns (client, Customer row)."""
    import re
    role = Role.query.filter_by(name="customer").first()
    u = User(username="cust1", role_id=role.id)
    u.set_password("password123")
    db.session.add(u)
    db.session.flush()
    cust = Customer(user_id=u.id, name="Test Customer", phone="9000000000")
    db.session.add(cust)
    db.session.commit()

    login_page = client.get("/login")
    token = re.search(rb'name="csrf_token" value="([^"]+)"', login_page.data).group(1).decode()
    client.post("/login", data={"username": "cust1", "password": "password123", "csrf_token": token},
               follow_redirects=True)
    return client, cust
