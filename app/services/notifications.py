"""Notifications, sent for real when a provider is configured in .env, and logged (not sent)
otherwise - so the app runs out of the box with zero external accounts.

- SMS and WhatsApp go through Twilio's REST API (plain HTTPS call, no SDK dependency needed).
- Email goes through SMTP (Python's built-in smtplib - works with Gmail, Outlook, SES, etc.).

A failed send is logged and swallowed rather than raised, so a billing or signup flow never
breaks just because a text message didn't go out.
"""
import base64
import logging
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from email.mime.text import MIMEText

from flask import current_app

from app.extensions import db
from app.models.analytics import Reminder, StockAlertSubscription
from app.models.base import utcnow
from app.models.customer import PatientMedication

log = logging.getLogger("medicore.notify")

TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def _twilio_configured():
    c = current_app.config
    return bool(c.get("TWILIO_ACCOUNT_SID") and c.get("TWILIO_AUTH_TOKEN"))


def _send_twilio(to, body, whatsapp=False):
    c = current_app.config
    sid, token = c["TWILIO_ACCOUNT_SID"], c["TWILIO_AUTH_TOKEN"]
    from_number = c["TWILIO_WHATSAPP_FROM"] if whatsapp else c["TWILIO_SMS_FROM"]
    if not from_number:
        log.warning("Twilio is configured but %s sender number is missing - skipping real send.",
                    "TWILIO_WHATSAPP_FROM" if whatsapp else "TWILIO_SMS_FROM")
        return False
    to_number = f"whatsapp:{to}" if whatsapp and not to.startswith("whatsapp:") else to
    data = urllib.parse.urlencode({"From": from_number, "To": to_number, "Body": body}).encode()
    req = urllib.request.Request(TWILIO_API.format(sid=sid), data=data, method="POST")
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                log.error("Twilio responded %s for %s", resp.status, to)
            return ok
    except urllib.error.HTTPError as e:
        log.error("Twilio send failed (%s): %s", e.code, e.read()[:300])
        return False
    except Exception:
        log.exception("Twilio send failed for %s", to)
        return False


def _smtp_configured():
    c = current_app.config
    return bool(c.get("SMTP_HOST") and c.get("SMTP_FROM"))


def _send_email(to, subject, body):
    c = current_app.config
    msg = MIMEText(body)
    msg["Subject"], msg["From"], msg["To"] = subject, c["SMTP_FROM"], to
    try:
        with smtplib.SMTP(c["SMTP_HOST"], c["SMTP_PORT"], timeout=10) as server:
            if c.get("SMTP_USE_TLS", True):
                server.starttls()
            if c.get("SMTP_USER"):
                server.login(c["SMTP_USER"], c["SMTP_PASSWORD"])
            server.sendmail(c["SMTP_FROM"], [to], msg.as_string())
        return True
    except Exception:
        log.exception("Email send failed for %s", to)
        return False


def send(channel, to, message, subject=None):
    """channel: 'sms', 'whatsapp' or 'email'. Returns True if actually delivered to a provider,
    False if it only fell back to logging (or the real send failed)."""
    to = (to or "").strip()
    if not to:
        return False

    if channel in ("sms", "whatsapp") and _twilio_configured():
        if _send_twilio(to, message, whatsapp=(channel == "whatsapp")):
            return True
        log.info("[%s fallback-log] to=%s :: %s", channel, to, message)
        return False

    if channel == "email" and _smtp_configured():
        if _send_email(to, subject or current_app.config["STORE_NAME"], message):
            return True
        log.info("[email fallback-log] to=%s :: %s", to, message)
        return False

    # No provider configured for this channel: just log it, so local dev always "works".
    log.info("[%s] to=%s :: %s", channel, to, message)
    return False


def notify_restock(medicine_id):
    """Tell 'notify me' subscribers once the medicine is sellable again."""
    from app.services.availability import available_quantity
    subs = StockAlertSubscription.query.filter_by(medicine_id=medicine_id, notified=False).all()
    if not subs or available_quantity(medicine_id) <= 0:
        return 0
    for s in subs:
        channel = "email" if "@" in s.contact else "sms"
        send(channel, s.contact, f"{s.medicine.brand_name} is back in stock at MediCore Pharmacy.",
            subject="Back in stock")
        s.notified = True
    db.session.commit()
    return len(subs)


def schedule_refill_reminders(days_ahead=3):
    """Create a reminder for every regular medicine that runs out within `days_ahead` days."""
    created = 0
    today = date.today()
    for pm in PatientMedication.query.filter_by(active=True).all():
        if not pm.last_refill_on:
            continue
        runs_out = pm.last_refill_on + timedelta(days=pm.days_supply or 30)
        if runs_out - today <= timedelta(days=days_ahead):
            exists = Reminder.query.filter_by(patient_medication_id=pm.id, sent=False).first()
            if exists:
                continue
            db.session.add(Reminder(
                customer_id=pm.customer_id, patient_medication_id=pm.id, remind_on=today,
                channel="email" if (pm.customer and pm.customer.email) else "sms",
                message=f"Your {pm.medicine.brand_name} runs out around {runs_out:%d %b}. Reorder from MediCore."))
            created += 1
    db.session.commit()
    return created


def dispatch_reminders():
    sent = 0
    for r in Reminder.query.filter(Reminder.sent.is_(False), Reminder.remind_on <= date.today()).all():
        contact = (r.customer.email if r.channel == "email" else r.customer.phone) or r.customer.phone \
            or r.customer.email
        send(r.channel, contact, r.message, subject="Refill reminder")
        r.sent, r.sent_at = True, utcnow()
        sent += 1
    db.session.commit()
    return sent
