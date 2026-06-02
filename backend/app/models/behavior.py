from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserBehaviorLog(Base):
    __tablename__ = "behavior_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(30))
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    need_id: Mapped[Optional[int]] = mapped_column(ForeignKey("needs.id"), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class UserPreferenceProfile(Base):
    __tablename__ = "preference_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    preference_vector: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    behavioral_tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_reflected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reflection_count: Mapped[int] = mapped_column(Integer, default=0)
