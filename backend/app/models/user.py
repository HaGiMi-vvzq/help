from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    skill_tags: Mapped[Optional[list]] = mapped_column(JSON)
    profile_embedding: Mapped[Optional[list]] = mapped_column(JSON)
    avatar: Mapped[Optional[str]] = mapped_column(Text)
    school: Mapped[Optional[str]] = mapped_column(String(100))
    extra: Mapped[Optional[dict]] = mapped_column(JSON)
    rating_score: Mapped[float] = mapped_column(Float, default=5.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
