import os
import uuid

from werkzeug.security import check_password_hash, generate_password_hash  # noqa: F401
from werkzeug.utils import secure_filename


def unique_filename(original):
    """Random name for uploads so files can't be guessed or overwritten."""
    ext = os.path.splitext(secure_filename(original))[1].lower()
    return f"{uuid.uuid4().hex}{ext}"


def mask_phone(phone):
    phone = phone or ""
    return phone[:2] + "*" * max(len(phone) - 4, 0) + phone[-2:] if len(phone) > 4 else phone


def is_safe_next(target):
    """Only allow redirects to paths on this site."""
    return bool(target) and target.startswith("/") and not target.startswith("//")
