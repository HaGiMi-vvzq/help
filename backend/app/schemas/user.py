from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    username: str
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
