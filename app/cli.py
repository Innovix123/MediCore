import click

from app.extensions import db


def register_cli(app):
    @app.cli.command("init-db")
    def init_db_cmd():
        """Create tables, views, indexes and triggers."""
        from database.init_db import init_database
        init_database()
        click.echo("Database ready.")

    @app.cli.command("seed")
    def seed_cmd():
        """Load sample medicines, users and sales history."""
        from database.init_db import init_database
        from database.seed_data import seed
        init_database()
        seed()

    @app.cli.command("send-reminders")
    def reminders_cmd():
        """Create and send refill reminders (run daily)."""
        from app.services import notifications
        click.echo(f"created {notifications.schedule_refill_reminders()}, sent {notifications.dispatch_reminders()}")

    @app.cli.command("expire-reservations")
    def expire_cmd():
        """Release expired pickup reservations (run every few minutes)."""
        from app.services.availability import expire_reservations
        click.echo(f"released {expire_reservations()}")
