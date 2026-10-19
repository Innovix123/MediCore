from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    """Naive UTC timestamp (SQLite stores naive datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Money as float keeps SQLite happy; round at the service layer.
Money = db.Numeric(10, 2, asdecimal=False)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SoftDeleteMixin:
    """Records are hidden, never physically removed."""
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = utcnow()
