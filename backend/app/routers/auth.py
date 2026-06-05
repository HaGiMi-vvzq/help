from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.events import get_event_bus
from app.guardrails.rate_limiter import get_login_rate_limiter, get_rate_limiter
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

LOGIN_RATE_LIMIT_PER_MINUTE = 5
REGISTER_RATE_LIMIT_PER_MINUTE = 3


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/register", response_model=AuthResponse)
async def register(data: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    limiter = get_rate_limiter()
    if not limiter.check_ip(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    try:
        result = await auth_service.register(db, data, get_event_bus())
        # Audit log
        import asyncio
        from app.services.audit_service import log_registration
        client_ip = request.client.host if request.client else None
        asyncio.create_task(log_registration(result.user.id, data.username, client_ip))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    limiter = get_login_rate_limiter()
    if not limiter.check_ip(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    try:
        result = await auth_service.login(db, data.username, data.password)
        # Audit log
        import asyncio
        from app.services.audit_service import log_login
        client_ip = request.client.host if request.client else None
        asyncio.create_task(log_login(result.user.id, data.username, client_ip))
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Request a password reset token. In production, token would be emailed."""
    try:
        token = await auth_service.create_reset_token(db, data.username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "message": "重置令牌已生成", "token": token}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using the token from forgot-password."""
    try:
        auth_service.validate_password_strength(data.new_password)
        await auth_service.reset_password(db, data.token, data.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "message": "密码已重置，请重新登录"}
