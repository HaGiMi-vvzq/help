"""Reset the SQLite database. Requires explicit confirmation.

Usage:
    cd backend
    python reset_db.py          # prompts for confirmation
    python reset_db.py --yes    # skips confirmation (use in scripts)
"""

import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reset_db")

BACKEND_DIR = Path(__file__).resolve().parent

DB_FILES = [
    BACKEND_DIR / "app.db",
    BACKEND_DIR / "app.db-wal",
    BACKEND_DIR / "app.db-shm",
]

SKILL_GRAPH = BACKEND_DIR / "skill_graph.json"
BACKUP_DIR = BACKEND_DIR / "db_backups"


def count_users() -> int:
    """Return current user count for the confirmation prompt."""
    try:
        import asyncio
        from sqlalchemy import select, func
        from app.core.database import async_session
        from app.models.user import User

        async def _count():
            async with async_session() as db:
                result = await db.execute(select(func.count()).select_from(User))
                return result.scalar() or 0

        return asyncio.run(_count())
    except Exception:
        return -1


def reset_database():
    deleted = []
    for db_file in DB_FILES:
        if db_file.exists():
            db_file.unlink()
            deleted.append(str(db_file.name))
            logger.info("Deleted: %s", db_file.name)

    if SKILL_GRAPH.exists():
        SKILL_GRAPH.unlink()
        deleted.append(SKILL_GRAPH.name)
        logger.info("Deleted: %s", SKILL_GRAPH.name)

    if not deleted:
        logger.info("No database files found. Nothing to reset.")
        return

    logger.info("Database reset complete. Deleted: %s", ", ".join(deleted))
    logger.info("Users can now register real accounts through the web interface.")


def main():
    parser = argparse.ArgumentParser(description="Reset the SQLite database")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    user_count = count_users()

    if not args.yes:
        print("=" * 60)
        print("  WARNING: This will permanently delete all database data!")
        print("=" * 60)

        if user_count >= 0:
            print(f"  Current users in database: {user_count}")
        print(f"  Files to be deleted:")
        for f in DB_FILES + [SKILL_GRAPH]:
            if f.exists():
                print(f"    - {f.name}")
        if BACKUP_DIR.exists():
            backups = sorted(BACKUP_DIR.iterdir())
            if backups:
                print(f"  Last backup available: {backups[-1].name}")
        print()
        confirm = input("  Type 'YES' (uppercase) to confirm reset: ").strip()
        if confirm != "YES":
            print("  Reset cancelled.")
            return

    reset_database()


if __name__ == "__main__":
    main()
