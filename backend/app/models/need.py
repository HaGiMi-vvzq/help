from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Need(Base):
    __tablename__ = "needs"
    __table_args__ = (
        Index("ix_needs_status_type", "status", "type"),
        Index("ix_needs_user_id", "user_id"),
        Index("ix_needs_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    req_tags: Mapped[Optional[list]] = mapped_column(JSON)
    need_embedding: Mapped[Optional[list]] = mapped_column(JSON)
    selection_mode: Mapped[Optional[str]] = mapped_column(String(20), default="single")
    selected_user_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="\u5f00\u653e")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship()
