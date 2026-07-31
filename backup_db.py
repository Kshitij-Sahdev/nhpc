"""
NHPC Weather Warning System — Database Backup Utility.

Creates timestamped backups of the SQLite database using SQLite's
built-in backup() API, which safely copies the database without
locking or corrupting it during concurrent reads/writes.

Usage:
    python backup_db.py                  # Backup with defaults
    python backup_db.py --retain 14      # Keep last 14 backups

Can also be called programmatically:
    from backup_db import backup_database
    backup_database()
"""

import os
import sys
import glob
import sqlite3
from datetime import datetime
from typing import Optional

from log import setup_logging, get_logger
from config import get_settings

logger = get_logger("nhpc.backup")


def backup_database(
    db_path: Optional[str] = None,
    backup_dir: Optional[str] = None,
    retain: Optional[int] = None,
) -> Optional[str]:
    """Create a timestamped backup of the SQLite database.

    Uses SQLite's C-level backup API via ``conn.backup()`` for a
    consistent, non-locking snapshot.

    Args:
        db_path: Source database path. Defaults to config DB_PATH.
        backup_dir: Directory for backups. Defaults to ``data/backups/``.
        retain: Number of backups to keep. Defaults to config DB_BACKUP_RETAIN.

    Returns:
        Path to the created backup file, or None if backup failed.
    """
    settings = get_settings()

    if db_path is None:
        db_path = settings.DB_PATH
    if backup_dir is None:
        backup_dir = os.path.join(settings.DATA_DIR, "backups")
    if retain is None:
        retain = settings.DB_BACKUP_RETAIN

    if not os.path.exists(db_path):
        logger.warning("Database file not found at %s — nothing to backup.", db_path)
        return None

    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"nhpc_weather_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    try:
        logger.info("Starting database backup: %s -> %s", db_path, backup_path)

        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_path)

        source.backup(dest)

        dest.close()
        source.close()

        backup_size = os.path.getsize(backup_path)
        logger.info(
            "Backup completed successfully: %s (%.2f MB)",
            backup_filename,
            backup_size / (1024 * 1024),
        )

        # Prune old backups
        _prune_old_backups(backup_dir, retain)

        return backup_path

    except Exception as e:
        logger.error("Database backup failed: %s", e, exc_info=True)
        # Clean up partial backup
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass
        return None


def _prune_old_backups(backup_dir: str, retain: int) -> None:
    """Delete old backups, keeping only the most recent `retain` files.

    Args:
        backup_dir: Directory containing backup files.
        retain: Number of most recent backups to keep.
    """
    pattern = os.path.join(backup_dir, "nhpc_weather_backup_*.db")
    backups = sorted(glob.glob(pattern))

    if len(backups) <= retain:
        return

    to_delete = backups[: len(backups) - retain]
    for old_backup in to_delete:
        try:
            os.remove(old_backup)
            logger.info("Pruned old backup: %s", os.path.basename(old_backup))
        except OSError as e:
            logger.warning("Failed to prune backup %s: %s", old_backup, e)


if __name__ == "__main__":
    import argparse

    setup_logging()

    parser = argparse.ArgumentParser(description="NHPC Database Backup Utility")
    parser.add_argument(
        "--retain",
        type=int,
        default=None,
        help="Number of backups to retain (default: from config)",
    )
    args = parser.parse_args()

    result = backup_database(retain=args.retain)
    if result:
        print(f"Backup saved to: {result}")
    else:
        print("Backup failed. Check logs for details.")
        sys.exit(1)
