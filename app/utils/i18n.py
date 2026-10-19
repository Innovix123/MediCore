"""English-only text lookup. Kept as a small t() helper (rather than hardcoding strings in every
template) so the app can add another language later without touching every page again."""
from flask import session

TRANSLATIONS = {
    "en": {
        "nav_find": "Find medicine", "nav_upload": "Upload prescription", "nav_orders": "My orders",
        "nav_profile": "Profile", "nav_cart": "Cart", "nav_login": "Log in", "nav_logout": "Log out",
        "hero_title": "Check if your medicine is in stock",
        "hero_sub": "Search by brand, generic name or composition before you make the trip.",
        "search_btn": "Search", "search_placeholder": "e.g. Dolo 650, paracetamol",
        "in_stock": "In stock", "low": "Low stock", "out": "Out of stock",
        "rx_required": "Prescription required", "alternatives": "Available alternatives",
        "notice": "Availability is updated regularly; please confirm at the store. "
                  "Prescription-only medicines still need a valid prescription to buy.",
    },
}


def current_lang():
    return "en"


def t(key):
    return TRANSLATIONS["en"].get(key, key)
