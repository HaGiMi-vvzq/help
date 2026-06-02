from datetime import datetime

from pydantic import BaseModel


class NeedCreate(BaseModel):
    type: str
    title: str
    description: str
    selection_mode: str = "single"


class NeedUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class SelectUsersRequest(BaseModel):
    user_ids: list[int]


class NeedApplicationCreate(BaseModel):
    message: str = ""


class NeedApplicationReview(BaseModel):
    owner_reply: str | None = None


class NeedApplicationResponse(BaseModel):
    id: int
    need_id: int
    applicant_user_id: int
    owner_user_id: int | None = None
    applicant_username: str = ""
    applicant_skill_tags: list[str] | None = None
    message: str
    status: str
    owner_reply: str | None = None
    owner_username: str | None = None
    need_title: str | None = None
    need_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NeedApplicationListResponse(BaseModel):
    items: list[NeedApplicationResponse]


class NeedResponse(BaseModel):
    id: int
    user_id: int
    username: str = ""
    type: str
    title: str
    description: str
    req_tags: list[str] | None = None
    selection_mode: str = "single"
    selected_user_ids: list[int] | None = None
    status: str
    application_count: int = 0
    can_apply: bool | None = None
    my_application_status: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NeedListResponse(BaseModel):
    items: list[NeedResponse]
    total: int
    page: int
    page_size: int
