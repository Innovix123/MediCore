from flask import Blueprint, jsonify, request

from app.extensions import limiter
from app.models.medicine import Medicine
from app.services.availability import find_medicines, search_with_availability

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/medicines/search")
@limiter.limit("30 per minute")
def search():
    """Public. Returns availability STATUS only: no quantities, costs or supplier data."""
    return jsonify(search_with_availability(request.args.get("q", "")))


@api_bp.route("/medicines/suggest")
@limiter.limit("60 per minute")
def suggest():
    """Autocomplete: up to 6 medicine names."""
    names = []
    for m in find_medicines(request.args.get("q", ""), limit=6):
        if m.brand_name not in names:
            names.append(m.brand_name)
    return jsonify(names)
