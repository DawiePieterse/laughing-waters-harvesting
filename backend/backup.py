"""Full data backup: zips the SQLite DB + worker photos, retains the most
recent MAX_BACKUPS, and runs itself automatically once a day at 02:00 via a
background daemon thread - no scheduling library needed for a single daily
job. Backup files never include the app's source code (already in git),
only the data that changes at runtime."""
import os
import sqlite3
import tempfile
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


def _snapshot_db(destination: str) -> None:
    """A consistent copy of the live database, via SQLite's own backup API.

    Plain-copying the .db file (what this used to do) reads whatever bytes
    happen to be on disk. In `delete` journal mode - which this database uses
    - a write in flight has the .db partially updated with the rollback data
    sitting in a separate -journal file the zip never captured, so a copy
    taken mid-transaction is unrecoverable. The nightly 02:00 run is usually
    safe simply because nobody is picking, but Settings has a "Backup Now"
    button that gets pressed during harvest while field devices sync every
    10 seconds. The failure is silent - the zip writes fine and only turns
    out to be corrupt when someone tries to restore it.

    sqlite3's backup() coordinates with any concurrent writer and yields a
    self-consistent snapshot.
    """
    source = sqlite3.connect(DB_PATH)
    try:
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def create_backup() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.zip"
    path = os.path.join(BACKUPS_DIR, filename)
    snapshot = None
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(DB_PATH):
                fd, snapshot = tempfile.mkstemp(suffix=".db", dir=BACKUPS_DIR)
                os.close(fd)
                os.remove(snapshot)  # sqlite3 wants to create the file itself
                _snapshot_db(snapshot)
                zf.write(snapshot, arcname="laughing_waters.db")
            for root, _, files in os.walk(PHOTOS_DIR):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.join("photos", os.path.relpath(full, PHOTOS_DIR))
                    zf.write(full, arcname=arcname)
    finally:
        # Never leave a stray .db beside the archives - _backup_filenames only
        # matches backup_*.zip, so a leftover would sit there unnoticed.
        if snapshot and os.path.exists(snapshot):
            os.remove(snapshot)
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
        except Exception as e:
            # Don't let one bad night kill the thread - try again tomorrow.
            # But say so: swallowing this silently meant a backup that failed
            # every night left no trace anywhere, and the one place it would
            # be noticed is the day someone needs to restore.
            print(f"[backup] nightly backup FAILED: {e!r}", flush=True)


def start_backup_scheduler() -> None:
    threading.Thread(target=_scheduler_loop, daemon=True).start()
