"""Runs the jobs that used to need manual `flask send-reminders` / `flask expire-reservations`
calls (or an external cron job) automatically, inside the app itself.

- expire-reservations: every 5 minutes, releases pickup holds whose time ran out.
- refill reminders: once a day, creates reminders for medicines about to run out, then sends
  whatever reminders are due.

Guarded so it only starts ONE scheduler even though Flask's debug reloader runs create_app()
twice, and never during pytest (app.config["TESTING"] skips it - see app/__init__.py).
"""
import atexit
import logging

log = logging.getLogger("medicore.scheduler")
_scheduler = None


def _run_reservation_expiry(app):
    with app.app_context():
        from app.services.availability import expire_reservations
        try:
            n = expire_reservations()
            if n:
                log.info("Released %d expired reservation(s).", n)
        except Exception:
            log.exception("expire_reservations job failed")


def _run_reminders(app):
    with app.app_context():
        from app.services.notifications import dispatch_reminders, schedule_refill_reminders
        try:
            created = schedule_refill_reminders()
            sent = dispatch_reminders()
            log.info("Reminders: created %d, sent %d.", created, sent)
        except Exception:
            log.exception("reminders job failed")


def start_scheduler(app):
    """Starts once per process. `run.py` disables Werkzeug's auto-reloader specifically so this
    never has to guess whether it's running in a reloader "parent" or "child" process - with the
    reloader on, both processes import and run this at module load time, before Flask even knows
    whether debug/reloader will be used, so there's no reliable way to tell them apart here.
    If you run under multiple gunicorn/uWSGI workers in production, each worker will start its
    own copy of this scheduler; move reminders/reservation-expiry to a real cron job or a single
    dedicated worker (e.g. Celery beat) at that point instead of relying on this in-process one."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        log.warning("APScheduler is not installed - reminders/reservation expiry must be run manually "
                    "(flask send-reminders / flask expire-reservations) or via an external cron job.")
        return None

    sched = BackgroundScheduler(daemon=True, timezone="Asia/Kolkata")
    sched.add_job(_run_reservation_expiry, "interval", minutes=5, args=[app], id="expire_reservations")
    sched.add_job(_run_reminders, "cron", hour=9, minute=0, args=[app], id="refill_reminders")
    sched.start()
    atexit.register(lambda: sched.shutdown(wait=False))
    _scheduler = sched
    log.info("Background scheduler started: reservation expiry every 5 min, reminders daily at 09:00 IST.")
    return sched
