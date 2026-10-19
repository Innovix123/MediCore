"""Stock availability: the single source of truth used by billing AND public search.

available = quantity in NON-EXPIRED batches - quantity held by ACTIVE reservations
"""
from datetime import date
from difflib import get_close_matches

from sqlalchemy import and_, func, or_

from app.extensions import db
from app.models.analytics import SearchLog
from app.models.base import utcnow
from app.models.inventory_ops import Branch
from app.models.medicine import Batch, Medicine
from app.models.order import Reservation
from app.utils.i18n import t


def batch_quantities(medicine_ids, branch_id=None, pharmacy_id=None):
    """Total sellable (non-expired) quantity per medicine. Scope to ONE branch with `branch_id`,
    or to every branch of ONE pharmacy with `pharmacy_id` (used for purchasing decisions, which
    are made pharmacy-wide rather than per branch). With neither, sums across everyone."""
    if not medicine_ids:
        return {}
    q = (db.session.query(Batch.medicine_id, func.coalesce(func.sum(Batch.quantity), 0))
         .filter(Batch.medicine_id.in_(medicine_ids), Batch.expiry_date > date.today(), Batch.quantity > 0))
    if branch_id:
        q = q.filter(Batch.branch_id == branch_id)
    elif pharmacy_id:
        q = q.join(Branch, Batch.branch_id == Branch.id).filter(Branch.pharmacy_id == pharmacy_id)
    return dict(q.group_by(Batch.medicine_id).all())


def reserved_quantities(medicine_ids, branch_id=None):
    if not medicine_ids:
        return {}
    q = (db.session.query(Reservation.medicine_id, func.coalesce(func.sum(Reservation.quantity), 0))
         .filter(Reservation.medicine_id.in_(medicine_ids), Reservation.status == "active",
                 Reservation.expires_at > utcnow()))
    if branch_id:
        q = q.filter(Reservation.branch_id == branch_id)
    return dict(q.group_by(Reservation.medicine_id).all())


def available_quantities(medicine_ids, branch_id=None, pharmacy_id=None):
    stock = batch_quantities(medicine_ids, branch_id, pharmacy_id)
    held = reserved_quantities(medicine_ids, branch_id)   # pharmacy-wide reservation totals aren't needed yet
    return {mid: max(int(stock.get(mid, 0)) - int(held.get(mid, 0)), 0) for mid in medicine_ids}


def available_quantity(medicine_id, branch_id=None, pharmacy_id=None):
    return available_quantities([medicine_id], branch_id, pharmacy_id)[medicine_id]


def stock_status(qty, reorder_level):
    if qty <= 0:
        return "out"
    if qty <= reorder_level:
        return "low"
    return "in_stock"


def expire_reservations():
    """Release holds whose time ran out. Run from `flask expire-reservations` or a scheduler."""
    rows = Reservation.query.filter(Reservation.status == "active", Reservation.expires_at <= utcnow()).all()
    for r in rows:
        r.status = "expired"
    db.session.commit()
    return len(rows)


def alternatives_for(medicine, limit=3):
    """Same composition (or same generic) medicines that are in stock, cheapest first."""
    cands = (Medicine.query.filter(Medicine.deleted_at.is_(None), Medicine.id != medicine.id,
                                   or_(func.lower(Medicine.composition) == medicine.composition.lower(),
                                       and_(func.lower(Medicine.generic_name) == medicine.generic_name.lower(),
                                            Medicine.strength == medicine.strength)))
             .all())
    avail = available_quantities([c.id for c in cands])
    ok = sorted((c for c in cands if avail[c.id] > 0), key=lambda c: c.mrp)
    return ok[:limit]


def find_medicines(query, limit=10):
    """Match brand, generic, composition or strength. Every word must match somewhere.
    Falls back to fuzzy matching so typos like 'paracetmol' still work."""
    query = (query or "").strip()
    if len(query) < 2:
        return []
    base = Medicine.query.filter(Medicine.deleted_at.is_(None))
    q = base
    for token in query.split():
        like = f"%{token}%"
        q = q.filter(or_(Medicine.brand_name.ilike(like), Medicine.generic_name.ilike(like),
                         Medicine.composition.ilike(like), Medicine.strength.ilike(like),
                         Medicine.barcode == token))
    rows = q.order_by(Medicine.brand_name).limit(limit).all()
    if rows:
        return rows

    everything = base.all()
    keys = {}
    for m in everything:
        keys.setdefault(m.brand_name.lower(), m)
        keys.setdefault(m.generic_name.lower(), m)
    close = get_close_matches(query.lower(), list(keys), n=limit, cutoff=0.6)
    seen, out = set(), []
    for k in close:
        if keys[k].id not in seen:
            seen.add(keys[k].id)
            out.append(keys[k])
    return out


def search_with_availability(query, log=True):
    meds = find_medicines(query)
    avail = available_quantities([m.id for m in meds])
    results = []
    for m in meds:
        status = stock_status(avail[m.id], m.reorder_level)
        alts = []
        if status == "out":
            alts = [{"id": a.id, "name": a.brand_name, "strength": a.strength, "price": a.mrp}
                    for a in alternatives_for(m)]
        results.append({
            "id": m.id, "name": m.brand_name, "generic": m.generic_name, "composition": m.composition,
            "strength": m.strength, "form": m.form, "price": m.mrp, "schedule": m.schedule,
            "requires_prescription": m.needs_rx, "status": status, "status_label": t(status),
            "alternatives": alts,
        })
    if log and query and len(query.strip()) >= 2:
        db.session.add(SearchLog(query=query.strip().lower()[:120], results_count=len(results),
                                 out_of_stock_count=sum(1 for r in results if r["status"] == "out")))
        db.session.commit()
    return results
