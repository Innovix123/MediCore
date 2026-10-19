from datetime import date, datetime


def allowed_file(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def to_int(value, default=None, minimum=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return default if (minimum is not None and n < minimum) else n


def to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_date(value, default=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


def today():
    return date.today()
