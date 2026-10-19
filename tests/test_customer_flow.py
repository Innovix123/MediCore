import re
from datetime import date, timedelta

from app.extensions import db
from app.models import Batch, Medicine


def _csrf(html):
    return re.search(rb'name="csrf_token" value="([^"]+)"', html).group(1).decode()


def _buyable_medicine(name="Calpol 500"):
    m = Medicine(brand_name=name, generic_name="Paracetamol", composition="Paracetamol 500mg",
                strength="500 mg", mrp=18, gst_percent=12, reorder_level=10)
    db.session.add(m)
    db.session.flush()
    db.session.add(Batch(medicine_id=m.id, batch_no="X1", expiry_date=date.today() + timedelta(days=200),
                         quantity=50))
    db.session.commit()
    return m


def test_every_placed_order_appears_in_order_history(app, logged_in_customer, medicine):
    """Regression test: placing several orders should show ALL of them on the orders page,
    not just the most recent one."""
    client, _ = logged_in_customer
    second_medicine = _buyable_medicine()

    for med in (medicine, second_medicine):
        cart_page = client.get("/cart")
        token = _csrf(cart_page.data)
        client.post("/cart/add", data={"medicine_id": med.id, "quantity": 1, "csrf_token": token},
                   follow_redirects=True)
        token2 = _csrf(client.get("/cart").data)
        res = client.post("/checkout", data={"fulfilment": "pickup", "csrf_token": token2}, follow_redirects=True)
        assert res.status_code == 200

    orders_page = client.get("/orders")
    html = orders_page.data.decode()
    assert "#1" in html
    assert "#2" in html


def test_guest_is_sent_to_login_first(client):
    """The very first thing an unauthenticated visitor sees is the login/create-account page."""
    res = client.get("/", follow_redirects=True)
    assert res.status_code == 200
    assert b"Create account" in res.data or b"Log in" in res.data
    assert b"Check if your medicine is in stock" not in res.data  # not the search page yet


def test_logged_in_customer_sees_logout_link(logged_in_customer):
    """Every logged-in role, including 'customer', must see a way to log out."""
    client, _ = logged_in_customer
    res = client.get("/")
    assert b"Log out" in res.data
