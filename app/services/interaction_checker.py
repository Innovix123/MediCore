"""Drug interaction and allergy warnings shown at dispensing time."""
import re
from itertools import combinations

from app.models.customer import PatientAllergy, PatientMedication
from app.models.medicine import Medicine
from app.models.prescription import DrugInteraction

SEVERITY_RANK = {"minor": 1, "moderate": 2, "major": 3}

# An allergy to a class should flag every member of the class.
ALLERGY_CLASSES = {
    "penicillin": {"penicillin", "amoxicillin", "ampicillin", "cloxacillin", "piperacillin"},
    "nsaid": {"ibuprofen", "diclofenac", "aspirin", "naproxen", "aceclofenac", "ketorolac"},
    "sulfa": {"sulfamethoxazole", "sulfasalazine", "sulfadiazine"},
}
_STRENGTH = re.compile(r"[\d.]+\s*(mg|mcg|g|ml|iu|%|units?)?", re.I)


def ingredients(med):
    """'Amoxicillin 500mg + Clavulanic Acid 125mg' -> {'amoxicillin', 'clavulanic acid'}"""
    text = med.composition or med.generic_name or ""
    parts = re.split(r"[+,/]", text)
    return {_STRENGTH.sub("", p).strip().lower() for p in parts if _STRENGTH.sub("", p).strip()}


def _allergy_hit(allergen, ings):
    allergen = allergen.strip().lower()
    group = ALLERGY_CLASSES.get(allergen, {allergen})
    return any(g in i or i in g for g in group for i in ings)


def check(medicine_ids, customer_id=None, family_member_id=None):
    """Return a list of warnings, most severe first."""
    meds = Medicine.query.filter(Medicine.id.in_(medicine_ids)).all()
    warnings = []

    if customer_id:
        allergies = PatientAllergy.query.filter(PatientAllergy.customer_id == customer_id).all()
        for a in allergies:
            if a.family_member_id not in (None, family_member_id):
                continue
            for m in meds:
                if _allergy_hit(a.allergen, ingredients(m)):
                    warnings.append({"type": "allergy", "severity": "major",
                                     "message": f"{m.brand_name} may trigger the recorded allergy to {a.allergen}."})

    groups = [(m.brand_name, ingredients(m)) for m in meds]
    if customer_id:
        current = (PatientMedication.query
                   .filter_by(customer_id=customer_id, active=True).all())
        for pm in current:
            if pm.medicine_id not in medicine_ids:
                groups.append((f"{pm.medicine.brand_name} (current medicine)", ingredients(pm.medicine)))

    table = {frozenset((r.drug_a.lower(), r.drug_b.lower())): r for r in DrugInteraction.query.all()}
    seen = set()
    for (name_a, ing_a), (name_b, ing_b) in combinations(groups, 2):
        for a in ing_a:
            for b in ing_b:
                row = table.get(frozenset((a, b)))
                key = (name_a, name_b, a, b)
                if row and key not in seen:
                    seen.add(key)
                    warnings.append({"type": "interaction", "severity": row.severity,
                                     "message": f"{name_a} + {name_b}: {row.note}"})
    warnings.sort(key=lambda w: -SEVERITY_RANK[w["severity"]])
    return warnings
