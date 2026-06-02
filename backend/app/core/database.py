import os
import shutil
import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Enable WAL mode for better concurrency and crash safety
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


async def migrate_sqlite_schema(conn: AsyncConnection) -> None:
    """Best-effort additive migrations for the local demo database."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    async def existing_columns(table: str) -> set[str]:
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
        return {row[1] for row in result.fetchall()}

    async def ensure_columns(table: str, columns: dict[str, str]) -> None:
        current = await existing_columns(table)
        for name, ddl in columns.items():
            if name in current:
                continue
            logger.info("Applying SQLite migration: %s.%s", table, name)
            await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    await ensure_columns(
        "agent_sessions",
        {
            "summary": "TEXT",
            "planning_state": "JSON",
            "status": "VARCHAR(20) DEFAULT 'active'",
            "updated_at": "DATETIME",
        },
    )
    await ensure_columns(
        "agent_tasks",
        {
            "parent_task_id": "INTEGER",
            "task_type": "VARCHAR(50)",
            "assigned_agent": "VARCHAR(50)",
            "input_data": "JSON",
            "result": "JSON",
            "error": "TEXT",
            "error_code": "VARCHAR(50)",
            "retry_count": "INTEGER DEFAULT 0",
            "need_id": "INTEGER",
            "match_id": "INTEGER",
            "file_id": "INTEGER",
            "updated_at": "DATETIME",
        },
    )
    await ensure_columns(
        "agent_files",
        {
            "extracted_info": "JSON",
            "embedding": "JSON",
        },
    )
    await ensure_columns(
        "needs",
        {
            "selection_mode": "VARCHAR(20) DEFAULT 'single'",
            "selected_user_ids": "JSON",
        },
    )
    await conn.exec_driver_sql("UPDATE agent_sessions SET updated_at = COALESCE(updated_at, created_at)")
    await conn.exec_driver_sql("UPDATE agent_tasks SET retry_count = COALESCE(retry_count, 0)")


async def get_db():
    async with async_session() as session:
        yield session


def backup_db():
    """Create a timestamped backup of the database file."""
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), "..", "..", db_path)
    db_path = os.path.normpath(db_path)
    if os.path.exists(db_path):
        backup_dir = os.path.join(os.path.dirname(db_path), "db_backups")
        os.makedirs(backup_dir, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"app_{ts}.db")
        shutil.copy2(db_path, backup_path)
        logger.info("DB backup created: %s", backup_path)
        # Keep only last 5 backups
        backups = sorted(os.listdir(backup_dir))
        while len(backups) > 5:
            os.remove(os.path.join(backup_dir, backups[0]))
            backups.pop(0)
