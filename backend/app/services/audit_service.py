"""Audit logging service — structured operation logs for compliance and debugging."""

import json
import logging
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.database import async_session

logger = logging.getLogger("audit")

AUDIT_DIR = Path(__file__).resolve().parents[2] / "logs" / "audit"


async def log_operation(
    user_id: int,
    action: str,
    resource: str,
    resource_id: int | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
):
    """Write a structured audit log entry."""
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "detail": detail or {},
        "ip": ip_address,
    }

    # Persistent DB log
    try:
        from app.models.behavior import UserBehaviorLog
        async with async_session() as db:
            log = UserBehaviorLog(
                user_id=user_id,
                event_type=action,
                extra_data={"resource": resource, "resource_id": resource_id, "detail": detail},
            )
            db.add(log)
            await db.commit()
    except Exception:
        pass

    # File-based audit log (always works, survives DB issues)
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        audit_file = AUDIT_DIR / f"audit-{date_str}.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to write audit log")


async def log_registration(user_id: int, username: str, ip: str | None = None):
    await log_operation(user_id, "user_registered", "user", user_id,
                        {"username": username}, ip)


async def log_login(user_id: int, username: str, ip: str | None = None):
    await log_operation(user_id, "user_logged_in", "user", user_id,
                        {"username": username}, ip)


async def log_need_created(user_id: int, need_id: int, title: str, ip: str | None = None):
    await log_operation(user_id, "need_created", "need", need_id,
                        {"title": title}, ip)


async def log_need_deleted(user_id: int, need_id: int, title: str, ip: str | None = None):
    await log_operation(user_id, "need_deleted", "need", need_id,
                        {"title": title}, ip)


async def log_message_sent(user_id: int, message_id: int, receiver_id: int, ip: str | None = None):
    await log_operation(user_id, "message_sent", "message", message_id,
                        {"receiver_id": receiver_id}, ip)


async def log_admin_action(admin_id: int, action: str, target_user_id: int | None = None):
    await log_operation(admin_id, f"admin_{action}", "admin_action",
                        target_user_id, {"action": action})
