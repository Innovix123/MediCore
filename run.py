from app import create_app
from database.init_db import init_database
from database.seed_data import seed

app = create_app()

# Runs at import time, not just under `python run.py`, so this also fires correctly under a
# production server (e.g. `gunicorn run:app`) that imports this module without ever calling
# `app.run()`. Both init_database() and seed() are safe to call repeatedly: create_all() only
# creates tables that don't exist yet, and seed() checks for existing users and skips if the
# database already has data - so this is a no-op after the very first boot.
with app.app_context():
    init_database()
    seed()

if __name__ == "__main__":
    # use_reloader=False: with the reloader on, Werkzeug runs this whole file in two processes
    # (a "parent" that watches for file changes and a "child" that actually serves requests),
    # which would start two competing background schedulers. Keeping it off means one process,
    # one scheduler - at the cost of auto-restart-on-save. Restart manually after editing code,
    # or re-enable use_reloader=True if you prefer auto-restart over that (jobs would then just
    # run twice in dev, which is harmless here, only wasteful).
    app.run(debug=True, use_reloader=False)