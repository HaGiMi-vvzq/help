from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = "新对话"


class SessionResponse(BaseModel):
    id: int
    user_id: int
    title: str
    summary: str | None = None
    planning_state: dict | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    token_count: int | None = None
    extra_metadata: dict | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: int
    session_id: int
    parent_task_id: int | None = None
    task_type: str | None = None
    goal: str
    status: str
    assigned_agent: str | None = None
    input_data: dict | None = None
    result: dict | None = None
    error: str | None = None
    error_code: str | None = None
    retry_count: int = 0
    need_id: int | None = None
    match_id: int | None = None
    file_id: int | None = None
    children: list["TaskResponse"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class FileUploadResponse(BaseModel):
    id: int
    session_id: int
    filename: str
    file_type: str
    extracted_info: dict | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str


class PlanRequest(BaseModel):
    goal: str


class NeedDraft(BaseModel):
    type: str
    title: str
    description: str
    selection_mode: str = "single"


class ConfirmPublishRequest(BaseModel):
    draft: NeedDraft | list[NeedDraft] | None = None


class SearchKnowledgeRequest(BaseModel):
    query: str
