"""Read-only report queries used by the dashboard and the reports page."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models.analytics import SearchLog
from app.models.medicine import Batch, Medicine
from app.models.order import Order
from app.models.prescription import PrescriptionUpload
from app.models.sales import Invoice, InvoiceItem
from app.models.supplier import GoodsReceipt, PurchaseOrder
from app.services.availability import available_quantities


def low_stock():
    meds = Medicine.query.filter(Medicine.deleted_at.is_(None)).order_by(Medicine.brand_name).all()
    avail = available_quantities([m.id for m in meds])
    return [{"medicine": m, "available": avail[m.id]} for m in meds if avail[m.id] <= m.reorder_level]


def near_expiry(days=None):
    """Batches expiring soon, earliest first (sell these first: FEFO)."""
    days = days or current_app.config["NEAR_EXPIRY_DAYS"]
    return (Batch.query.join(Medicine).filter(Batch.quantity > 0, Batch.expiry_date > date.today(),
                                              Batch.expiry_date <= date.today() + timedelta(days=days))
            .order_by(Batch.expiry_date).all())


def expired_stock():
    return Batch.query.filter(Batch.quantity > 0, Batch.expiry_date <= date.today()).order_by(Batch.expiry_date).all()


def dead_stock(days=None):
    days = days or current_app.config["DEAD_STOCK_DAYS"]
    since = datetime.combine(date.today() - timedelta(days=days), time.min)
    moving = {r[0] for r in db.session.query(InvoiceItem.medicine_id).join(Invoice)
              .filter(Invoice.created_at >= since).distinct()}
    meds = Medicine.query.filter(Medicine.deleted_at.is_(None)).all()
    avail = available_quantities([m.id for m in meds])
    return [{"medicine": m, "available": avail[m.id]} for m in meds if avail[m.id] > 0 and m.id not in moving]


def daily_sales(day=None, branch_id=None):
    day = day or date.today()
    start, end = datetime.combine(day, time.min), datetime.combine(day + timedelta(days=1), time.min)
    q = Invoice.query.filter(Invoice.created_at >= start, Invoice.created_at < end)
    if branch_id:
        q = q.filter(Invoice.branch_id == branch_id)
    invoices = q.all()
    by_mode = defaultdict(float)
    for i in invoices:
        by_mode[i.payment_mode] += i.total
    return {"day": day, "count": len(invoices), "total": round(sum(i.total for i in invoices), 2),
            "gst": round(sum(i.gst_amount for i in invoices), 2),
            "by_mode": {k: round(v, 2) for k, v in by_mode.items()}}


def sales_trend(days=14):
    start = date.today() - timedelta(days=days - 1)
    totals = defaultdict(float)
    for i in Invoice.query.filter(Invoice.created_at >= datetime.combine(start, time.min)).all():
        totals[i.created_at.date()] += i.total
    return [(start + timedelta(days=n), round(totals[start + timedelta(days=n)], 2)) for n in range(days)]


def top_sellers(days=30, limit=5):
    since = datetime.combine(date.today() - timedelta(days=days), time.min)
    return (db.session.query(Medicine.brand_name, func.sum(InvoiceItem.quantity), func.sum(InvoiceItem.line_total))
            .select_from(InvoiceItem).join(Invoice).join(Medicine, InvoiceItem.medicine_id == Medicine.id)
            .filter(Invoice.created_at >= since).group_by(Medicine.id)
            .order_by(func.sum(InvoiceItem.line_total).desc()).limit(limit).all())


def profit_by_medicine(days=30):
    """Net-of-GST revenue minus purchase cost of the exact batches sold."""
    since = datetime.combine(date.today() - timedelta(days=days), time.min)
    rows = (db.session.query(Medicine.brand_name, func.sum(InvoiceItem.quantity),
                             func.sum(InvoiceItem.line_total - InvoiceItem.gst_amount),
                             func.sum(InvoiceItem.quantity * Batch.purchase_price))
            .select_from(InvoiceItem).join(Invoice).join(Medicine, InvoiceItem.medicine_id == Medicine.id)
            .join(Batch, InvoiceItem.batch_id == Batch.id)
            .filter(Invoice.created_at >= since).group_by(Medicine.id).all())
    out = [{"name": n, "units": int(u), "revenue": round(r or 0, 2), "cost": round(c or 0, 2),
            "profit": round((r or 0) - (c or 0), 2)} for n, u, r, c in rows]
    return sorted(out, key=lambda r: -r["profit"])


def unmet_demand(days=30):
    since = datetime.combine(date.today() - timedelta(days=days), time.min)
    return (db.session.query(SearchLog.query, func.count(SearchLog.id),
                             func.sum(SearchLog.results_count), func.sum(SearchLog.out_of_stock_count))
            .filter(SearchLog.created_at >= since).group_by(SearchLog.query)
            .having((func.sum(SearchLog.results_count) == 0) | (func.sum(SearchLog.out_of_stock_count) > 0))
            .order_by(func.count(SearchLog.id).desc()).limit(25).all())


def supplier_dues():
    return [g for g in GoodsReceipt.query.order_by(GoodsReceipt.due_date).all() if g.outstanding > 0]


def dashboard_kpis():
    today = daily_sales()
    return {
        "today_total": today["total"], "today_count": today["count"],
        "low_stock": len(low_stock()), "near_expiry": len(near_expiry()), "expired": len(expired_stock()),
        "pending_rx": PrescriptionUpload.query.filter_by(status="pending").count(),
        "open_orders": Order.query.filter(Order.status.in_(("placed", "packed", "awaiting_prescription",
                                                           "out_for_delivery", "ready_for_pickup"))).count(),
        "open_pos": PurchaseOrder.query.filter(PurchaseOrder.status.in_(("draft", "sent"))).count(),
    }
