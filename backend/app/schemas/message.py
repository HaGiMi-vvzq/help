from datetime import datetime

from pydantic import BaseModel


class MessageCreate(BaseModel):
    need_id: int
    receiver_id: int
    content: str


class MessageResponse(BaseModel):
    id: int
    need_id: int
    sender_id: int
    receiver_id: int
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationPreview(BaseModel):
    other_user_id: int
    other_username: str
    need_id: int
    last_message: str
    last_time: datetime
