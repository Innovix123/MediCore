"""Copy the SQLite database into backups/ with a timestamp.
Run manually (`python database/backup.py`) or schedule it with cron / Windows Task Scheduler.
Test a restore now and then: copy a backup over medicore.db and start the app."""
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "medicore.db")
DEST_DIR = os.path.join(ROOT, "backups")
KEEP = 14


def main():
    if not os.path.exists(SRC):
        sys.exit("medicore.db not found - nothing to back up.")
    os.makedirs(DEST_DIR, exist_ok=True)
    dest = os.path.join(DEST_DIR, f"medicore_{datetime.now():%Y%m%d_%H%M%S}.db")
    shutil.copy2(SRC, dest)
    print("Backup written:", dest)
    for old in sorted(f for f in os.listdir(DEST_DIR) if f.endswith(".db"))[:-KEEP]:
        os.remove(os.path.join(DEST_DIR, old))


if __name__ == "__main__":
    main()
