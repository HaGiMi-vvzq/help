from pydantic import BaseModel


class MatchResult(BaseModel):
    user_id: int
    score: float
    reason: str
    complementarity: str = ""
    username: str = ""
    school: str = ""
    bio: str = ""
    extra: dict | None = None
    skill_tags: list[str] = []


class MatchResponse(BaseModel):
    need: "NeedResponse"
    matches: list[MatchResult]

    model_config = {"from_attributes": True}


class FeedbackRequest(BaseModel):
    feedback: int  # 1-5


class MatchProgress(BaseModel):
    stage: str
    message: str
    data: dict = {}


from app.schemas.need import NeedResponse
