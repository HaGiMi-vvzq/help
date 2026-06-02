from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.events import get_event_bus
from app.guardrails.rate_limiter import get_login_rate_limiter, get_rate_limiter
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_RATE_LIMIT_PER_MINUTE = 5
REGISTER_RATE_LIMIT_PER_MINUTE = 3


@router.post("/register", response_model=AuthResponse)
async def register(data: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    limiter = get_rate_limiter()
    if not limiter.check_ip(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    try:
        return await auth_service.register(db, data, get_event_bus())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    limiter = get_login_rate_limiter()
    if not limiter.check_ip(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    try:
        return await auth_service.login(db, data.username, data.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
