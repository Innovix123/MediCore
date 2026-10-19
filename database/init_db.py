"""Create tables, then apply the SQL views, indexes and triggers."""
import os

from app.extensions import db

SQL_DIR = os.path.dirname(os.path.abspath(__file__))


def init_database():
    db.create_all()
    if db.engine.dialect.name != "sqlite":
        print("Non-SQLite database: run database/postgres_extras.sql manually if you need it.")
        return
    raw = db.engine.raw_connection()
    try:
        for name in ("views.sql", "indexes.sql", "triggers.sql"):
            with open(os.path.join(SQL_DIR, name), encoding="utf-8") as fh:
                raw.executescript(fh.read())
        raw.commit()
    finally:
        raw.close()
