"""Admin API router: stats, user management, need management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.user import (
    AdminNeedItem,
    AdminStats,
    AdminUserItem,
    AdminUserUpdate,
)
from app.services import admin_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── Stats ──────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats)
async def get_stats(
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_stats(db)


# ── Users ──────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, page, page_size)


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == admin_user.id and data.role is not None and data.role != "admin":
        raise HTTPException(400, "不能取消自己的管理员权限")
    user = await admin_service.update_user(db, user_id, data.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(404, "用户不存在")
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == admin_user.id:
        raise HTTPException(400, "不能删除自己")
    try:
        ok = await admin_service.delete_user(db, user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "用户不存在")
    return {"ok": True}


# ── Needs ──────────────────────────────────────────────────────────

@router.get("/needs")
async def list_needs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_needs(db, page, page_size)


class NeedStatusUpdate(BaseModel):
    status: str


@router.put("/needs/{need_id}")
async def update_need_status(
    need_id: int,
    data: NeedStatusUpdate,
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        need = await admin_service.update_need_status(db, need_id, data.status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not need:
        raise HTTPException(404, "需求不存在")
    return {"ok": True, "status": need.status}


@router.delete("/needs/{need_id}")
async def delete_need(
    need_id: int,
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ok = await admin_service.delete_need(db, need_id)
    if not ok:
        raise HTTPException(404, "需求不存在")
    return {"ok": True}
