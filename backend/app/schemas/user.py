from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    username: str
    role: str = "user"
    is_active: bool = True
    avatar: str | None = None
    bio: str | None = None
    skill_tags: list[str] | None = None
    school: str | None = None
    extra: dict | None = None
    rating_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    username: str | None = None
    bio: str | None = None
    skill_tags: list[str] | None = None
    school: str | None = None
    extra: str | None = None


class AdminUserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    total_needs: int
    open_needs: int
    matched_needs: int
    total_messages: int
    today_users: int
    today_needs: int


class AdminUserItem(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    school: str | None = None
    bio: str | None = None
    skill_tags: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminNeedItem(BaseModel):
    id: int
    user_id: int
    username: str
    type: str
    title: str
    description: str
    status: str
    selection_mode: str
    created_at: datetime

    model_config = {"from_attributes": True}
