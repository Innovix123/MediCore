from datetime import date, timedelta

from app.extensions import db
from app.models import Batch, Medicine


def test_search_endpoint_returns_json(client, medicine):
    res = client.get("/api/medicines/search?q=dolo")
    assert res.status_code == 200
    data = res.get_json()
    assert data[0]["name"] == "Dolo 650"
    assert data[0]["status"] == "in_stock"


def test_search_does_not_leak_cost_or_quantity(client, medicine):
    data = client.get("/api/medicines/search?q=dolo").get_json()
    dumped = str(data[0])
    assert "purchase_price" not in dumped and "quantity" not in dumped


def test_out_of_stock_shows_alternative(app, client):
    out = Medicine(brand_name="Crocin Advance", generic_name="Paracetamol", composition="Paracetamol 500mg",
                   strength="500 mg", mrp=20, gst_percent=12, reorder_level=10)
    alt = Medicine(brand_name="Calpol 500", generic_name="Paracetamol", composition="Paracetamol 500mg",
                  strength="500 mg", mrp=18, gst_percent=12, reorder_level=10)
    db.session.add_all([out, alt])
    db.session.flush()
    db.session.add(Batch(medicine_id=alt.id, batch_no="C1", expiry_date=date.today() + timedelta(days=100), quantity=20))
    db.session.commit()
    data = client.get("/api/medicines/search?q=crocin").get_json()
    assert data[0]["status"] == "out"
    assert data[0]["alternatives"][0]["name"] == "Calpol 500"


def test_home_redirects_guests_to_login(client):
    """Visiting the site with no session should land on the login/create-account page first."""
    res = client.get("/", follow_redirects=True)
    assert res.status_code == 200
    assert b"logo_600.png" in res.data
    assert b"Create account" in res.data or b"Log in" in res.data
