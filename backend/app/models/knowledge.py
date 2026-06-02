from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SkillCooccurrence(Base):
    __tablename__ = "skill_graph"
    __table_args__ = (UniqueConstraint("skill_a", "skill_b"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_a: Mapped[str] = mapped_column(String(100), index=True)
    skill_b: Mapped[str] = mapped_column(String(100), index=True)
    count: Mapped[int] = mapped_column(Integer, default=1)


class MatchMemory(Base):
    __tablename__ = "match_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    need_description: Mapped[str] = mapped_column(Text)
    need_embedding: Mapped[dict] = mapped_column(JSON)
    matched_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    score: Mapped[float] = mapped_column(Float)
    ai_reason: Mapped[str] = mapped_column(Text)
    feedback: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
