from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import AgentOrchestrator
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.events import get_event_bus
from app.guardrails.rate_limiter import get_rate_limiter
from app.models.need import Need as NeedModel
from app.models.user import User
from app.schemas.match import FeedbackRequest
from app.schemas.need import (
    NeedApplicationCreate,
    NeedApplicationListResponse,
    NeedApplicationReview,
    NeedCreate,
    NeedListResponse,
    NeedResponse,
    NeedUpdate,
    SelectUsersRequest,
)
from app.services import match_engine, need_application_service, need_service

router = APIRouter(prefix="/api/needs", tags=["needs"])


async def _notify_matching_complete(need_id: int):
    from app.core.database import async_session
    from app.models.message import Message
    from sqlalchemy import select as _s

    async with async_session() as bg_db:
        result = await bg_db.execute(_s(NeedModel).where(NeedModel.id == need_id))
        need = result.scalar_one_or_none()
        if need is None:
            return

        matches = await match_engine.get_matches(bg_db, need_id)
        bg_db.add(
            Message(
                need_id=need_id,
                sender_id=need.user_id,
                receiver_id=need.user_id,
                content=f"你的需求《{need.title}》匹配完成，共有{len(matches)}位候选人，点击查看结果。",
                is_read=False,
            )
        )
        await bg_db.commit()


@router.post("", response_model=NeedResponse)
async def create_need(
    data: NeedCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    limiter = get_rate_limiter()
    if not limiter.check_ip(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    need = await need_service.create_need(db, user, data, get_event_bus())
    match_engine.schedule_matching(need.id, get_event_bus(), notifier=_notify_matching_complete)
    return need


@router.get("/applications/mine", response_model=NeedApplicationListResponse)
async def list_my_applications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await need_application_service.list_my_applications(db, user.id)
    return NeedApplicationListResponse(items=items)


@router.post("/applications/{application_id}/accept")
async def accept_application(
    application_id: int,
    data: NeedApplicationReview,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        application = await need_application_service.review_application(
            db,
            application_id=application_id,
            owner=user,
            accepted=True,
            owner_reply=data.owner_reply,
            event_bus=get_event_bus(),
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return application


@router.post("/applications/{application_id}/reject")
async def reject_application(
    application_id: int,
    data: NeedApplicationReview,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        application = await need_application_service.review_application(
            db,
            application_id=application_id,
            owner=user,
            accepted=False,
            owner_reply=data.owner_reply,
            event_bus=get_event_bus(),
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return application


@router.get("", response_model=NeedListResponse)
async def list_needs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    type: str | None = Query(None, alias="type"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await need_service.get_needs(
        db,
        page,
        page_size,
        status,
        type,
        viewer_id=user.id,
    )
    return NeedListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/mine", response_model=list[NeedResponse])
async def list_my_needs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await need_service.get_my_needs(db, user.id)


@router.get("/selected/mine", response_model=list[NeedResponse])
async def list_my_selected_needs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await need_service.get_my_selected_needs(db, user.id)


@router.get("/{need_id}", response_model=NeedResponse)
async def get_need(
    need_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    return need


@router.post("/{need_id}/apply")
async def apply_to_need(
    need_id: int,
    data: NeedApplicationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await _get_need_orm(db, need_id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    try:
        return await need_application_service.create_application(
            db,
            need=need,
            applicant=user,
            message=data.message,
            event_bus=get_event_bus(),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{need_id}/applications", response_model=NeedApplicationListResponse)
async def get_need_applications(
    need_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await _get_need_orm(db, need_id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if need.user_id != user.id:
        raise HTTPException(403, "只能查看自己需求收到的申请")
    items = await need_application_service.list_need_applications(db, need=need)
    return NeedApplicationListResponse(items=items)


@router.put("/{need_id}", response_model=NeedResponse)
async def update_need(
    need_id: int,
    data: NeedUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if need.user_id != user.id:
        raise HTTPException(403, "只能编辑自己的需求")
    return await need_service.update_need(db, await _get_need_orm(db, need_id), data)


@router.delete("/{need_id}")
async def delete_need(
    need_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if need.user_id != user.id:
        raise HTTPException(403, "只能删除自己的需求")
    orm_need = await _get_need_orm(db, need_id)
    await match_engine.cancel_matching(need_id)
    await need_service.delete_need(db, orm_need)
    return {"ok": True}


@router.post("/{need_id}/close")
async def close_need(
    need_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if need.user_id != user.id:
        raise HTTPException(403, "只能关闭自己的需求")
    orm_need = await _get_need_orm(db, need_id)
    return await need_service.update_need(db, orm_need, NeedUpdate(status="关闭"))


@router.post("/{need_id}/select", response_model=NeedResponse)
async def select_matched_users(
    need_id: int,
    data: SelectUsersRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need_detail = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need_detail is None:
        raise HTTPException(404, "需求不存在")
    if need_detail.user_id != user.id:
        raise HTTPException(403, "只能为自己的需求选择匹配用户")
    orm_need = await _get_need_orm(db, need_id)
    return await need_service.select_users(db, orm_need, data, get_event_bus())


@router.post("/{need_id}/deselect/{target_user_id}", response_model=NeedResponse)
async def deselect_matched_user(
    need_id: int,
    target_user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need_detail = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need_detail is None:
        raise HTTPException(404, "需求不存在")
    if need_detail.user_id != user.id:
        raise HTTPException(403, "只能为自己的需求取消选择")
    orm_need = await _get_need_orm(db, need_id)
    return await need_service.deselect_user(db, orm_need, target_user_id)


async def _get_need_orm(db: AsyncSession, need_id: int):
    from sqlalchemy import select as _s

    result = await db.execute(
        _s(NeedModel).options(selectinload(NeedModel.user)).where(NeedModel.id == need_id)
    )
    return result.unique().scalar_one_or_none()


@router.get("/{need_id}/matches")
async def get_matches(
    need_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if need.user_id != user.id:
        raise HTTPException(403, "只能查看自己需求的匹配结果")

    matches = await match_engine.get_matches(db, need_id)
    if not matches and not match_engine.is_matching_active(need_id):
        await match_engine.run_matching(db, need_id, get_event_bus())
        matches = await match_engine.get_matches(db, need_id)

    return {
        "need": need.model_dump(),
        "matches": [match.model_dump() for match in matches],
        "matching_active": match_engine.is_matching_active(need_id),
    }


def _extract_token(request: Request, token_query: str = "") -> str | None:
    """Extract JWT from cookie first, then query string (for SSE compatibility)."""
    cookie_token = request.cookies.get("auth_token")
    if cookie_token:
        return cookie_token
    if token_query:
        return token_query
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


@router.get("/{need_id}/matches/stream")
async def stream_matches(
    need_id: int,
    request: Request,
    token: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    user_id = None
    jwt = _extract_token(request, token)
    if jwt:
        from app.core.security import decode_access_token

        payload = decode_access_token(jwt)
        if payload is None:
            raise HTTPException(401, "Invalid token")
        user_id = payload.get("user_id")

    need = await need_service.get_need_detail(db, need_id, viewer_id=user_id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if user_id is not None and need.user_id != user_id:
        raise HTTPException(403, "只能查看自己需求的匹配结果")

    return StreamingResponse(
        match_engine.run_matching_stream(db, need_id, get_event_bus()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{need_id}/matches/refresh")
async def refresh_matches(
    need_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if need.user_id != user.id:
        raise HTTPException(403, "只能刷新自己需求的匹配结果")

    await match_engine.cancel_matching(need_id)
    await match_engine.run_matching(db, need_id, get_event_bus())
    matches = await match_engine.get_matches(db, need_id)
    return {
        "need": need.model_dump(),
        "matches": [match.model_dump() for match in matches],
        "matching_active": False,
    }


@router.post("/matches/{match_id}/feedback")
async def submit_feedback(
    match_id: int,
    data: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await match_engine.record_feedback(db, match_id, data.feedback, get_event_bus())
    return {"ok": True}


@router.post("/{need_id}/refine")
async def refine_need(
    need_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    result = await AgentOrchestrator.run_concierge(need.description, need.req_tags)
    return result


class ChatRequest(BaseModel):
    messages: list[dict] = []


@router.post("/{need_id}/chat")
async def chat_with_concierge(
    need_id: int,
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    need = await need_service.get_need_detail(db, need_id, viewer_id=user.id)
    if need is None:
        raise HTTPException(404, "需求不存在")
    if need.user_id != user.id:
        raise HTTPException(403, "只能对自己需求进行AI对话")

    match_list = await match_engine.get_matches(db, need_id)
    reply = await AgentOrchestrator.run_concierge_chat(
        need.description,
        need.req_tags or [],
        data.messages,
        [match.model_dump() for match in match_list] if match_list else [],
    )
    return {"reply": reply}


class PolishRequest(BaseModel):
    need_type: str
    title: str
    description: str
    selection_mode: str = "single"


class GenerateRequest(BaseModel):
    need_type: str
    title: str
    selection_mode: str = "single"


def _selection_mode_label(selection_mode: str | None) -> str:
    return "多人/多选" if selection_mode == "multi" else "单人/单选，只选择1位合作者"


def _align_description_with_selection_mode(text: str, selection_mode: str | None) -> str:
    if selection_mode != "single":
        return text
    replacements = {
        "2-3个": "1位",
        "2-3 个": "1 位",
        "两三个": "1位",
        "几个": "1位",
        "多位": "1位",
        "多个": "1位",
        "一群": "1位",
        "队友们": "队友",
        "同学们": "同学",
        "组建团队": "寻找搭档",
        "招募团队": "寻找搭档",
    }
    aligned = text
    for source, target in replacements.items():
        aligned = aligned.replace(source, target)
    return aligned


@router.post("/polish")
async def polish_description(
    data: PolishRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.adapters.deepseek_adapter import DeepSeekChatAdapter
    from app.integrations.client import get_ai_client
    from app.integrations.model_router import route
    from app.prompts.registry import PromptRegistry
    from app.services.user_context import build_user_context

    user_context = await build_user_context(db, user)

    client = get_ai_client()
    cfg = route("concierge")
    adapter = DeepSeekChatAdapter(client, model=cfg["model"])

    messages = PromptRegistry.render(
        "polish_description",
        {
            "user_context": user_context,
            "need_type": data.need_type,
            "title": data.title,
            "description": data.description,
            "selection_mode_label": _selection_mode_label(data.selection_mode),
        },
    )

    polished = await adapter.chat(messages, temperature=0.7, max_tokens=512)
    return {"result": _align_description_with_selection_mode(polished, data.selection_mode)}


@router.post("/generate")
async def generate_description(
    data: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.adapters.deepseek_adapter import DeepSeekChatAdapter
    from app.integrations.client import get_ai_client
    from app.integrations.model_router import route
    from app.prompts.registry import PromptRegistry
    from app.services.user_context import build_user_context

    user_context = await build_user_context(db, user)

    client = get_ai_client()
    cfg = route("concierge")
    adapter = DeepSeekChatAdapter(client, model=cfg["model"])

    messages = PromptRegistry.render(
        "generate_description",
        {
            "user_context": user_context,
            "need_type": data.need_type,
            "title": data.title,
            "selection_mode_label": _selection_mode_label(data.selection_mode),
        },
    )

    generated = await adapter.chat(messages, temperature=0.8, max_tokens=512)
    return {"result": _align_description_with_selection_mode(generated, data.selection_mode)}


class BehaviorLogRequest(BaseModel):
    event_type: str
    target_user_id: int | None = None
    need_id: int | None = None


@router.post("/behavior/log")
async def log_behavior(
    data: BehaviorLogRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.behavior import UserBehaviorLog
    from app.services.reflection_service import check_and_reflect

    db.add(
        UserBehaviorLog(
            user_id=user.id,
            event_type=data.event_type,
            target_user_id=data.target_user_id,
            need_id=data.need_id,
        )
    )
    await db.commit()
    await check_and_reflect(db, user.id)
    return {"ok": True}
