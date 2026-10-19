"""Sample data so every screen has something to show.  Run: flask --app run seed"""
import random
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.models import (Batch, Branch, CreditLedger, Customer, Doctor, DrugInteraction, Expense, FamilyMember,
                        Invoice, InvoiceItem, Medicine, Offer, PatientAllergy, PatientMedication, Payment,
                        Permission, Pharmacy, Prescription, Role, SearchLog, Supplier, User)

PERMISSIONS = {
    "admin": ["inventory.manage", "reports.view", "purchase.manage", "staff.manage", "pos.use", "rx.verify"],
    "pharmacist": ["inventory.view", "pos.use", "rx.verify", "returns.process"],
    "cashier": ["pos.use", "returns.process"],
    "customer": ["orders.place"],
}
USERS = [  # username, password, role, full name
    ("admin", "admin123", "admin", "Store Owner"),
    ("pharmacist", "pharma123", "pharmacist", "Anjali Menon (Pharmacist)"),
    ("cashier", "cashier123", "cashier", "Rahul Nair (Cashier)"),
    ("demo", "demo12345", "customer", "Demo Customer"),
]
# brand, generic, composition, strength, form, category, schedule, mrp, gst, reorder, crit, cost%, batches[(no, days_to_expiry, qty)]
MEDS = [
    ("Dolo 650", "Paracetamol", "Paracetamol 650mg", "650 mg", "Tablet", "Fever & Pain", "OTC", 32, 12, 50, "E",
     [("DL2401", 200, 60), ("DL2409", 400, 90)]),
    ("Crocin Advance", "Paracetamol", "Paracetamol 500mg", "500 mg", "Tablet", "Fever & Pain", "OTC", 20, 12, 40, "E",
     [("CR2301", -20, 25)]),                                   # only an EXPIRED batch -> shows as out of stock
    ("Calpol 500", "Paracetamol", "Paracetamol 500mg", "500 mg", "Tablet", "Fever & Pain", "OTC", 18, 12, 40, "E",
     [("CP2405", 300, 120)]),
    ("Azithral 500", "Azithromycin", "Azithromycin 500mg", "500 mg", "Tablet", "Antibiotic", "H", 118, 12, 20, "E",
     [("AZ2402", 250, 12)]),                                   # low stock
    ("Augmentin 625", "Amoxicillin + Clavulanic Acid", "Amoxicillin 500mg + Clavulanic Acid 125mg", "625 mg", "Tablet",
     "Antibiotic", "H", 224, 12, 20, "E", [("AU2403", 180, 45)]),
    ("Mox 500", "Amoxicillin", "Amoxicillin 500mg", "500 mg", "Capsule", "Antibiotic", "H", 92, 12, 20, "E",
     [("MX2201", -30, 30), ("MX2406", 220, 40)]),
    ("Ecosprin 75", "Aspirin", "Aspirin 75mg", "75 mg", "Tablet", "Cardio", "OTC", 6, 5, 60, "V",
     [("EC2404", 28, 80), ("EC2410", 350, 150)]),             # first batch near expiry
    ("Warf 5", "Warfarin", "Warfarin 5mg", "5 mg", "Tablet", "Cardio", "H", 145, 5, 20, "V",
     [("WF2407", 300, 40)]),
    ("Brufen 400", "Ibuprofen", "Ibuprofen 400mg", "400 mg", "Tablet", "Fever & Pain", "OTC", 22, 12, 40, "D",
     [("BR2408", 260, 100)]),
    ("Cetzine 10", "Cetirizine", "Cetirizine 10mg", "10 mg", "Tablet", "Allergy & Cold", "OTC", 28, 12, 40, "D",
     [("CZ2411", 330, 90)]),
    ("Pantop 40", "Pantoprazole", "Pantoprazole 40mg", "40 mg", "Tablet", "Gastro", "H", 155, 12, 30, "E",
     [("PN2412", 280, 70)]),
    ("Glycomet 500", "Metformin", "Metformin 500mg", "500 mg", "Tablet", "Diabetes", "H", 24, 5, 60, "V",
     [("GL2413", 300, 200)]),
    ("Telma 40", "Telmisartan", "Telmisartan 40mg", "40 mg", "Tablet", "Cardio", "H", 98, 5, 40, "V",
     [("TL2414", 310, 110)]),
    ("Alprax 0.25", "Alprazolam", "Alprazolam 0.25mg", "0.25 mg", "Tablet", "Neuro", "H1", 42, 12, 15, "E",
     [("AL2415", 240, 30)]),
    ("Volini Gel", "Diclofenac", "Diclofenac 1% w/w", "30 g", "Gel", "Fever & Pain", "OTC", 135, 12, 15, "D",
     [("VG2416", 380, 25)]),
    ("Electral ORS", "ORS", "Oral Rehydration Salts", "21.8 g", "Powder", "Gastro", "OTC", 21, 5, 50, "E",
     [("EL2417", 120, 140)]),
    ("Mixtard 30", "Insulin", "Human Insulin 30/70", "40 IU/ml", "Injection", "Diabetes", "H", 168, 5, 15, "V",
     [("MT2418", 150, 22)]),
    ("Zerodol-P", "Aceclofenac + Paracetamol", "Aceclofenac 100mg + Paracetamol 325mg", "100/325 mg", "Tablet",
     "Fever & Pain", "H", 110, 12, 30, "D", [("ZP2419", 270, 65)]),
    ("Benadryl Syrup", "Diphenhydramine", "Diphenhydramine 14.08mg/5ml", "150 ml", "Syrup", "Allergy & Cold", "OTC",
     105, 12, 15, "D", [("BD2420", 45, 20)]),               # near expiry
    ("Betadine Ointment", "Povidone Iodine", "Povidone Iodine 5%", "20 g", "Ointment", "First aid", "OTC", 88, 12, 10,
     "D", [("BT2421", 320, 30)]),                              # dead stock (never sold)
]
INTERACTIONS = [
    ("warfarin", "aspirin", "major", "Bleeding risk is much higher. Avoid unless a doctor has prescribed both."),
    ("warfarin", "ibuprofen", "major", "NSAIDs raise bleeding risk with warfarin."),
    ("warfarin", "azithromycin", "moderate", "May increase warfarin effect; INR monitoring advised."),
    ("warfarin", "amoxicillin", "moderate", "May increase INR; monitor."),
    ("aspirin", "ibuprofen", "moderate", "Ibuprofen can block aspirin's heart-protective effect."),
    ("aspirin", "diclofenac", "moderate", "Two NSAIDs together raise stomach bleeding risk."),
    ("telmisartan", "ibuprofen", "moderate", "NSAIDs can weaken blood-pressure control and strain the kidneys."),
    ("aceclofenac", "aspirin", "moderate", "Two NSAIDs together raise stomach bleeding risk."),
]


def seed():
    if User.query.first():
        print("Database already has data - skipping seed.")
        return False
    rnd = random.Random(42)
    today = date.today()

    perms = {}
    for role_name, codes in PERMISSIONS.items():
        role = Role(name=role_name)
        for c in codes:
            perms.setdefault(c, Permission(code=c))
            role.permissions.append(perms[c])
        db.session.add(role)
    db.session.flush()
    roles = {r.name: r for r in Role.query.all()}

    pharmacy = Pharmacy(name="MediCore Pharmacy", slug="medicore", phone="0471-2000000",
                       email="owner@medicore.local", license_no="KL-PHM-20451", active=True)
    db.session.add(pharmacy)
    db.session.flush()

    branch_main = Branch(pharmacy_id=pharmacy.id, name="Main store - Thiruvananthapuram",
                         address="MG Road, Thiruvananthapuram, Kerala", phone="0471-2000001",
                         latitude=8.5241, longitude=76.9366, active=True)
    branch_kochi = Branch(pharmacy_id=pharmacy.id, name="Kochi branch", address="MG Road, Kochi, Kerala",
                          phone="0484-2000002", latitude=9.9312, longitude=76.2673, active=True)
    db.session.add_all([branch_main, branch_kochi])
    db.session.flush()

    users = {}
    for username, pw, role, full in USERS:
        u = User(username=username, full_name=full, email=f"{username}@medicore.local", role_id=roles[role].id,
                pharmacy_id=pharmacy.id if role != "customer" else None)
        u.set_password(pw)
        db.session.add(u)
        users[username] = u
    suppliers = [Supplier(pharmacy_id=pharmacy.id, name="Kerala Pharma Distributors", phone="0471-2000001",
                          payment_terms_days=30),
                 Supplier(pharmacy_id=pharmacy.id, name="Southern Medico Wholesale", phone="0471-2000002",
                          payment_terms_days=15)]
    db.session.add_all(suppliers)
    db.session.flush()

    meds = []
    for i, (brand, gen, comp, strength, form, cat, sched, mrp, gst, reorder, crit, batches) in enumerate(MEDS):
        m = Medicine(brand_name=brand, generic_name=gen, composition=comp, strength=strength, form=form,
                     category=cat, schedule=sched, requires_prescription=sched != "OTC", mrp=mrp,
                     gst_percent=gst, reorder_level=reorder, criticality=crit,
                     barcode=f"890{1000000 + i}", preferred_supplier_id=suppliers[i % 2].id,
                     description=f"{brand} contains {comp}.", uses=f"Used as directed by a doctor or pharmacist ({cat}).",
                     side_effects="Nausea, dizziness or allergic reaction in some people. Stop and consult a doctor if severe.")
        db.session.add(m)
        db.session.flush()
        for bi, (no, days, qty) in enumerate(batches):
            db.session.add(Batch(medicine_id=m.id, batch_no=no, branch_id=branch_main.id,
                                 expiry_date=today + timedelta(days=days), quantity=qty,
                                 purchase_price=round(mrp * 0.68, 2), supplier_id=m.preferred_supplier_id,
                                 received_on=today - timedelta(days=30)))
            # Give the Kochi branch its own (smaller, independent) stock of roughly every other medicine,
            # so switching branches in the UI actually shows different numbers.
            if i % 2 == 0 and bi == 0:
                db.session.add(Batch(medicine_id=m.id, batch_no=f"{no}-K", branch_id=branch_kochi.id,
                                     expiry_date=today + timedelta(days=max(days - 20, 30)),
                                     quantity=max(qty // 3, 5), purchase_price=round(mrp * 0.68, 2),
                                     supplier_id=m.preferred_supplier_id, received_on=today - timedelta(days=20)))
        meds.append(m)

    for a, b, sev, note in INTERACTIONS:
        db.session.add(DrugInteraction(drug_a=a, drug_b=b, severity=sev, note=note))

    customer = Customer(user_id=users["demo"].id, name="Demo Customer", phone="9847000001", email="demo@medicore.local",
                        address="TC 12/345, Pattom, Thiruvananthapuram")
    db.session.add(customer)
    db.session.flush()
    customer.allergies.append(PatientAllergy(allergen="Penicillin", note="Rash"))
    parent = FamilyMember(customer_id=customer.id, name="Mother", relation="Parent")
    customer.family.append(parent)
    by_brand = {m.brand_name: m for m in meds}
    customer.medications.append(PatientMedication(medicine_id=by_brand["Glycomet 500"].id, dosage="1 tablet twice daily",
                                                  days_supply=30, last_refill_on=today - timedelta(days=28)))
    doctor = Doctor(name="Dr. S. Pillai", registration_no="KMC 45821", phone="0471-2555555")
    db.session.add(doctor)
    db.session.flush()

    db.session.add(Offer(name="Monsoon fever care 10% off", discount_percent=10, category="Fever & Pain",
                         ends_on=today + timedelta(days=30)))
    for cat, amt, day in (("Rent", 25000, 1), ("Salaries", 42000, 1), ("Electricity", 4800, 5)):
        db.session.add(Expense(category=cat, amount=amt, spent_on=today.replace(day=min(day, today.day)),
                               note="Monthly"))
    for q, n, r, o in (("crocin", 14, 1, 1), ("insulin pen", 6, 0, 0), ("dolo", 9, 1, 0), ("becosules", 5, 0, 0)):
        for _ in range(n):
            db.session.add(SearchLog(query=q, results_count=r, out_of_stock_count=o,
                                     created_at=datetime.now() - timedelta(days=rnd.randint(0, 20))))

    # 60 days of sales history, all billed from the main branch (stock levels above are the CURRENT
    # levels, so this history does not touch quantities - it only picks an existing batch id to point at).
    sellable = [m for m in meds if m.brand_name not in ("Betadine Ointment", "Crocin Advance")]

    def main_branch_batch(med):
        return (Batch.query.filter_by(medicine_id=med.id, branch_id=branch_main.id)
                .filter(Batch.expiry_date > today).order_by(Batch.expiry_date.desc()).first())

    for back in range(60, -1, -1):
        day = today - timedelta(days=back)
        for _ in range(rnd.randint(3, 7)):
            when = datetime.combine(day, time(rnd.randint(9, 20), rnd.randint(0, 59)))
            picks = [m for m in rnd.sample(sellable, rnd.randint(1, 3)) if main_branch_batch(m)]
            if not picks:
                continue
            inv = Invoice(invoice_no=f"INV-H{back:03d}{rnd.randint(1000, 9999)}", cashier_id=users["cashier"].id,
                          branch_id=branch_main.id, payment_mode=rnd.choice(["cash", "upi", "upi", "card"]),
                          created_at=when)
            rx = None
            if any(m.schedule == "H1" for m in picks):
                rx = Prescription(customer_id=customer.id, doctor_id=doctor.id, issued_on=day,
                                  verified_by=users["pharmacist"].id)
                db.session.add(rx)
                db.session.flush()
                inv.prescription_id, inv.customer_id = rx.id, customer.id
            sub = gst_t = 0.0
            for m in picks:
                batch = main_branch_batch(m)
                qty = rnd.randint(1, 4)
                gross = m.mrp * qty
                gst = round(gross * m.gst_percent / (100 + m.gst_percent), 2)
                inv.items.append(InvoiceItem(medicine_id=m.id, batch_id=batch.id, quantity=qty, unit_price=m.mrp,
                                             gst_percent=m.gst_percent, gst_amount=gst, line_total=gross))
                sub += gross
                gst_t += gst
            inv.subtotal = inv.total = round(sub, 2)
            inv.gst_amount = round(gst_t, 2)
            db.session.add(inv)
    db.session.commit()
    print("Seeded. Logins -> admin/admin123, pharmacist/pharma123, cashier/cashier123, demo/demo12345")
    return True
