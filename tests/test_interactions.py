from datetime import date, timedelta

from app.extensions import db
from app.models import Batch, DrugInteraction, Medicine
from app.services import interaction_checker


def _med(name, comp, mrp=50):
    m = Medicine(brand_name=name, generic_name=name, composition=comp, mrp=mrp, gst_percent=12, reorder_level=5)
    db.session.add(m)
    db.session.flush()
    db.session.add(Batch(medicine_id=m.id, batch_no="B", expiry_date=date.today() + timedelta(days=100), quantity=20))
    return m


def test_major_interaction_detected(app):
    warfarin = _med("Warf 5", "Warfarin 5mg")
    aspirin = _med("Ecosprin", "Aspirin 75mg")
    db.session.add(DrugInteraction(drug_a="warfarin", drug_b="aspirin", severity="major", note="Bleeding risk"))
    db.session.commit()
    warnings = interaction_checker.check([warfarin.id, aspirin.id])
    assert any(w["type"] == "interaction" and w["severity"] == "major" for w in warnings)


def test_no_warning_when_no_match(app):
    a = _med("Dolo 650", "Paracetamol 650mg")
    b = _med("Cetzine", "Cetirizine 10mg")
    db.session.commit()
    assert interaction_checker.check([a.id, b.id]) == []
