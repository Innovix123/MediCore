import os
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    STORE_NAME = "MediCore Pharmacy"
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-only-change-me"
    _db_url = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "medicore.db"))
    if _db_url.startswith("postgresql://"):
        _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024          # 5 MB prescription uploads
    ALLOWED_UPLOADS = {"png", "jpg", "jpeg", "pdf"}

    # Business rules
    NEAR_EXPIRY_DAYS = 90        # "near-expiry" report window
    RESERVATION_HOURS = 2        # how long a pickup reservation is held
    DEAD_STOCK_DAYS = 90         # no sales in this many days = dead stock
    MAX_MANUAL_DISCOUNT = 20     # % a cashier may give at the counter

    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_HEADERS_ENABLED = True

    # --- Notification providers (all optional) ---
    # Leave any of these blank and that channel falls back to just logging the message, so the
    # app works out of the box without any external accounts.
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM", "")             # e.g. +15551234567
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")   # e.g. whatsapp:+14155238886

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SECRET_KEY = "test"
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "_test")
