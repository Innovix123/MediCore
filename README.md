# MediCore - Pharmacy Database Management System

Flask + SQLAlchemy web app covering customer ordering, pharmacist billing/verification,
and owner/admin inventory, purchasing, reports and compliance.

## Quick start (VS Code)

```bash
python -m venv venv
venv\Scripts\activate          # Windows. Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env
python run.py
```

Open http://127.0.0.1:5000 — the database and demo data are created automatically on first run.

**Demo logins:** admin/admin123 - pharmacist/pharma123 - cashier/cashier123 - demo/demo12345

In VS Code: `Ctrl+Shift+P` -> "Python: Select Interpreter" -> choose `./venv`. Press F5 to run with the debugger
(`.vscode/launch.json` is already set up).

## Useful commands

```bash
flask --app run init-db          # create tables + views/triggers (no sample data)
flask --app run seed             # add demo medicines, batches, users, 60 days of sales
flask --app run send-reminders   # generate and "send" refill reminders (schedule daily)
flask --app run expire-reservations   # release expired pickup holds (schedule every few minutes)
python database/backup.py        # copy medicore.db into backups/ with a timestamp
pytest                           # run the test suite
```

## Project layout

See the folder tree below. `app/models` is the database schema, `app/services` is business logic
(availability, billing, interactions, purchasing, forecasting, reports), `app/routes` are the
customer/pharmacist/admin/auth/API blueprints, and `database/` holds raw SQL (views, triggers, indexes)
plus seed and backup scripts.

## Multi-branch

The pharmacy ("MediCore Pharmacy", seeded automatically) can have several branches, each with its
own stock. Staff (admin/pharmacist/cashier) see a branch switcher in the bar at the top of every
page once logged in; billing, inventory counts, and the daily summary all scope to whichever
branch is currently selected. Admins manage branches at **More > Branches**. The demo data seeds
two branches (Thiruvananthapuram and Kochi) with independent stock so you can see the difference
immediately - try switching branches on the Billing page and searching for "Dolo 650" in each.

This is still a single pharmacy business with multiple locations, not a multi-tenant platform for
several unrelated pharmacies (that would need a `pharmacy_id` filter added throughout the admin
area, plus a way for each pharmacy to sign up - ask if you want that built out next).

## Real notifications (optional)

By default, "notifications" (restock alerts, refill reminders) are just logged to the console -
nothing external is required to run the app. To send real messages, fill in `.env`:

- **SMS / WhatsApp**: set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_SMS_FROM` (and/or
  `TWILIO_WHATSAPP_FROM`) from a Twilio account. No extra Python package needed - it calls
  Twilio's REST API directly.
- **Email**: set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (works with Gmail, a
  transactional email provider, etc.)

Leave any of these blank and that channel quietly falls back to logging instead of failing.

## Automatic scheduler

Reservation expiry (every 5 minutes) and refill reminders (daily at 09:00 IST) now run
automatically inside the app while it's running - you no longer have to call
`flask expire-reservations` / `flask send-reminders` by hand (those commands still exist if you
want to trigger them manually, e.g. for testing). This only runs while `python run.py` is active;
for a real always-on deployment behind gunicorn with multiple workers, move these to a proper
cron job or a dedicated worker instead, since each worker would otherwise start its own copy.

## Notes

- Default database is SQLite (`medicore.db`), zero setup. Switch to PostgreSQL by changing `DATABASE_URL`
  in `.env` — then also run `database/postgres_extras.sql` for trigram search and example triggers.
- `SECRET_KEY` and `DATABASE_URL` belong in `.env` (never commit it — see `.gitignore`).
- Prescriptions are stored in `uploads/`, which is also gitignored.
