from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import ProfileUpdate, UserResponse
from app.services import profile_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ExtractTagsRequest(BaseModel):
    bio: str


@router.post("/extract-tags")
async def extract_tags(
    data: ExtractTagsRequest,
    user: User = Depends(get_current_user),
):
    """从个人简介中 AI 提取技能标签。"""
    from app.skills.registry import SkillRegistry
    tag_skill = SkillRegistry.get("tag_extraction")
    result = await tag_skill.execute({"text": data.bio})
    return {"tags": result.get("tags", [])}


@router.get("/user/{user_id}")
async def get_user_basic(user_id: int, db: AsyncSession = Depends(get_db)):
    """返回用户基本信息（用于对话窗口显示对方用户名）。"""
    from sqlalchemy import select
    r = await db.execute(select(User).where(User.id == user_id))
    u = r.scalar_one_or_none()
    if u is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"id": u.id, "username": u.username}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.put("", response_model=UserResponse)
async def update_profile(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.update_profile(db, user, data)


ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type and file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(400, "仅支持 PNG、JPEG、GIF、WebP 格式的图片")
    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(400, "头像文件不能超过 2MB")
    import base64
    user.avatar = base64.b64encode(contents).decode()
    await db.commit()
    await db.refresh(user)
    return {"ok": True, "avatar": f"data:{file.content_type};base64,{user.avatar}"}
