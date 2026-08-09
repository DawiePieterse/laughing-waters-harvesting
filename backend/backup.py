"""Full data backup: zips the SQLite DB + worker photos, retains the most
recent MAX_BACKUPS, and runs itself automatically once a day at 02:00 via a
background daemon thread - no scheduling library needed for a single daily
job. Backup files never include the app's source code (already in git),
only the data that changes at runtime."""
import os
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone

from db import DATA_DIR, DB_PATH, PHOTOS_DIR

BACKUPS_DIR = os.path.join(DATA_DIR, "backups")
os.makedirs(BACKUPS_DIR, exist_ok=True)
MAX_BACKUPS = 14


def _backup_filenames() -> list[str]:
    return sorted(
        f for f in os.listdir(BACKUPS_DIR) if f.startswith("backup_") and f.endswith(".zip")
    )


def _prune_old_backups() -> None:
    stale = _backup_filenames()[:-MAX_BACKUPS] if MAX_BACKUPS > 0 else _backup_filenames()
    for name in stale:
        os.remove(os.path.join(BACKUPS_DIR, name))


def create_backup() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.zip"
    path = os.path.join(BACKUPS_DIR, filename)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_PATH):
            zf.write(DB_PATH, arcname="laughing_waters.db")
        for root, _, files in os.walk(PHOTOS_DIR):
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.join("photos", os.path.relpath(full, PHOTOS_DIR))
                zf.write(full, arcname=arcname)
    _prune_old_backups()
    return filename


def list_backups() -> list[dict]:
    result = []
    for name in reversed(_backup_filenames()):
        full = os.path.join(BACKUPS_DIR, name)
        stat = os.stat(full)
        result.append({
            "filename": name,
            "size_bytes": stat.st_size,
            # Tagged UTC so the browser can convert it to farm time; a naive
            # string would be read as local by JS and silently shifted.
            "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        })
    return result


def _seconds_until_next_2am() -> float:
    now = datetime.now()
    target = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _scheduler_loop() -> None:
    while True:
        time.sleep(_seconds_until_next_2am())
        try:
            create_backup()
        except Exception:
            pass  # don't let one bad night kill the thread - try again tomorrow


def start_backup_scheduler() -> None:
    threading.Thread(target=_scheduler_loop, daemon=True).start()
