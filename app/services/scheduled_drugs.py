"""Register of Schedule H1 / X drugs, generated from dispensing records."""
import csv
import io
from datetime import datetime, time, timedelta

from app.models.medicine import Medicine
from app.models.sales import Invoice, InvoiceItem

HEADERS = ["Date", "Invoice", "Drug", "Schedule", "Batch", "Qty", "Patient", "Doctor", "Doctor reg. no."]


def register_rows(start, end, schedules=("H1", "X")):
    q = (InvoiceItem.query.join(Invoice).join(Medicine, InvoiceItem.medicine_id == Medicine.id)
         .filter(Medicine.schedule.in_(schedules),
                 Invoice.created_at >= datetime.combine(start, time.min),
                 Invoice.created_at < datetime.combine(end + timedelta(days=1), time.min))
         .order_by(Invoice.created_at))
    rows = []
    for it in q.all():
        inv = it.invoice
        rx = inv.prescription
        doctor = rx.doctor if rx else None
        rows.append([f"{inv.created_at:%d-%m-%Y}", inv.invoice_no, it.medicine.display_name, it.medicine.schedule,
                     it.batch.batch_no, it.quantity, inv.customer.name if inv.customer else "Walk-in",
                     doctor.name if doctor else "", doctor.registration_no if doctor else ""])
    return rows


def to_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    w.writerows(rows)
    return buf.getvalue()
