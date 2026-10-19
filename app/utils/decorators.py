from functools import wraps

from flask import abort, session
from flask_login import current_user, login_required


def role_required(*roles):
    """Allow only users whose role name is in `roles` (403 otherwise)."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role_name not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


STAFF = ("admin", "pharmacist", "cashier")
CLINICAL = ("admin", "pharmacist")


def current_branch_id():
    """The branch a staff member is currently working from (switchable; defaults to branch 1)."""
    return session.get("branch_id", 1)
