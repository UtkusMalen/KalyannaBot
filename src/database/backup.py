import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/app/db_backups")
BACKUP_DIR.mkdir(exist_ok=True)

async def create_db_backup() -> bool:
    db_name = settings.db_name
    db_user = settings.db_user
    db_password = settings.db_password
    db_host = settings.db_host
    db_port = settings.db_port

    if not all([db_name, db_user, db_password, db_host, db_port]):
        logger.error("Backup failed: Database connection details are missing in settings.")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file_name = f"{db_name}_backup_{timestamp}.dump"
    backup_file_path = BACKUP_DIR / backup_file_name

    command = [
        "pg_dump",
        f"--dbname=postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}",
        "--format=custom",
        f"--file={backup_file_path}",
        "--no-password",
        "--verbose"
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    logger.info(f"Starting database backup to: {backup_file_path}")

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"Database backup successful. File: {backup_file_path}")
            if stdout:
                logger.debug(f"pg_dump stdout:\n{stdout.decode()}")
            await cleanup_old_backups()
            return True
        else:
            logger.error(f"Database backup failed with return code {process.returncode}.")
            if stderr:
                logger.error(f"pg_dump stderr:\n{stderr.decode()}")
            else:
                 logger.error("pg_dump produced no stderr output.")
            if stdout:
                 logger.error(f"pg_dump stdout (on error):\n{stdout.decode()}")
            if backup_file_path.exists():
                try:
                    backup_file_path.unlink()
                    logger.info(f"Removed incomplete backup file: {backup_file_path}")
                except OSError as e:
                    logger.error(f"Error removing incomplete backup file {backup_file_path}: {e}")
            return False

    except FileNotFoundError:
        logger.error("Backup failed: 'pg_dump' command not found. Make sure PostgreSQL client tools are installed and in PATH.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during backup: {e}", exc_info=True)
        return False

async def cleanup_old_backups(keep_days: int = 7):
    if keep_days <= 0:
        return

    now = datetime.now()
    cutoff = now - timedelta(days=keep_days)
    deleted_count = 0

    logger.info(f"Cleaning up backups older than {keep_days} days ({cutoff.strftime('%Y-%m-%d')})...")
    try:
        for item in BACKUP_DIR.iterdir():
            if item.is_file() and item.suffix == '.dump':
                try:
                    file_mod_time = datetime.fromtimestamp(item.stat().st_mtime)
                    if file_mod_time < cutoff:
                        item.unlink()
                        logger.info(f"Deleted old backup: {item.name}")
                        deleted_count += 1
                except OSError as e:
                    logger.error(f"Error deleting old backup file {item.name}: {e}")
                except Exception as e:
                     logger.error(f"Unexpected error processing file {item.name} for cleanup: {e}")
        logger.info(f"Backup cleanup finished. Deleted {deleted_count} old backups.")
    except Exception as e:
        logger.error(f"Error during backup cleanup process: {e}", exc_info=True)