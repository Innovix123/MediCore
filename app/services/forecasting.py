"""Demand forecast (moving average x seasonality) and ABC/VED analysis."""
from datetime import date, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.medicine import Medicine
from app.models.sales import Invoice, InvoiceItem

# Monsoon fevers and allergy season lift demand for some categories.
SEASONAL = {
    "Fever & Pain": {6: 1.2, 7: 1.4, 8: 1.4, 9: 1.2},
    "Allergy & Cold": {2: 1.2, 3: 1.3, 11: 1.2, 12: 1.2},
}


def units_sold(medicine_id, days=90):
    since = date.today() - timedelta(days=days)
    total = (db.session.query(func.coalesce(func.sum(InvoiceItem.quantity - InvoiceItem.returned_qty), 0))
             .join(Invoice).filter(InvoiceItem.medicine_id == medicine_id, Invoice.created_at >= since).scalar())
    return int(total or 0)


def forecast_next_30_days(medicine_id, history_days=90):
    med = db.session.get(Medicine, medicine_id)
    daily = units_sold(medicine_id, history_days) / history_days
    next_month = (date.today().month % 12) + 1
    factor = SEASONAL.get(med.category, {}).get(next_month, 1.0)
    return int(round(daily * 30 * factor))


def abc_ved_analysis():
    """A = top 70% of annual sales value, B = next 20%, C = the rest.
    V/E/D (vital/essential/desirable) comes from Medicine.criticality."""
    since = date.today() - timedelta(days=365)
    sold = dict(db.session.query(InvoiceItem.medicine_id, func.sum(InvoiceItem.line_total))
                .join(Invoice).filter(Invoice.created_at >= since).group_by(InvoiceItem.medicine_id).all())
    meds = Medicine.query.filter(Medicine.deleted_at.is_(None)).all()
    rows = sorted(((m, float(sold.get(m.id, 0) or 0)) for m in meds), key=lambda r: -r[1])
    total = sum(v for _, v in rows) or 1
    cum, out = 0.0, []
    for m, value in rows:
        cum += value
        share = cum / total
        abc = "A" if share <= 0.70 or not out else "B" if share <= 0.90 else "C"
        out.append({"medicine": m, "value": round(value, 2), "abc": abc, "ved": m.criticality,
                    "never_stock_out": m.criticality == "V"})
    return out
