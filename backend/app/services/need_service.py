from sqlalchemy import select, update
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import EventBus
from app.models.agent import AgentTask
from app.models.match import Match
from app.models.message import Message
from app.models.need import Need
from app.models.need_application import NeedApplication
from app.models.user import User
from app.schemas.message import MessageCreate
from app.schemas.need import NeedCreate, NeedResponse, NeedUpdate, SelectUsersRequest
from app.services import message_service, need_application_service
from app.skills.registry import SkillRegistry

OPEN_STATUS = "\u5f00\u653e"
MATCHED_STATUS = "\u5df2\u5339\u914d"


async def _build_need_response(
    db: AsyncSession,
    need: Need,
    *,
    viewer_id: int | None = None,
) -> NeedResponse:
    response = NeedResponse.model_validate(need)
    response.username = need.user.username if need.user else ""
    response.application_count = await need_application_service.count_need_applications(db, need.id)

    if viewer_id is None:
        return response

    if viewer_id == need.user_id:
        response.can_apply = False
        return response

    my_application = await need_application_service.get_my_application(db, need.id, viewer_id)
    response.my_application_status = my_application.status if my_application else None
    response.can_apply = need.status == OPEN_STATUS and (
        my_application is None or my_application.status in {"rejected", "withdrawn"}
    )
    return response


async def create_need(
    db: AsyncSession,
    user: User,
    data: NeedCreate,
    event_bus: EventBus | None = None,
) -> NeedResponse:
    tag_skill = SkillRegistry.get("tag_extraction")
    tags_result = await tag_skill.execute({"text": data.description})
    tags = tags_result.get("tags", [])

    embed_skill = SkillRegistry.get("embedding")
    emb_result = await embed_skill.execute({"text": " ".join(tags)})

    need = Need(
        user_id=user.id,
        type=data.type,
        title=data.title,
        description=data.description,
        req_tags=tags,
        need_embedding=emb_result["embedding"],
        selection_mode=data.selection_mode,
    )

    db.add(need)
    await db.commit()
    await db.refresh(need)
    need.user = user

    if event_bus:
        await event_bus.emit_background(
            "need_published",
            {"need_id": need.id, "user_id": user.id, "type": data.type},
        )

    return await _build_need_response(db, need, viewer_id=user.id)


async def get_needs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    need_type: str | None = None,
    user_id: int | None = None,
    viewer_id: int | None = None,
) -> tuple[list[NeedResponse], int]:
    base = select(Need).options(selectinload(Need.user))
    count_query = select(Need)

    query = base
    if status:
        query = query.where(Need.status == status)
        count_query = count_query.where(Need.status == status)
    if need_type:
        query = query.where(Need.type == need_type)
        count_query = count_query.where(Need.type == need_type)
    if user_id is not None:
        query = query.where(Need.user_id == user_id)
        count_query = count_query.where(Need.user_id == user_id)

    total_result = await db.execute(count_query)
    total = len(total_result.scalars().all())

    query = query.order_by(Need.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    needs = result.unique().scalars().all()
    return [await _build_need_response(db, need, viewer_id=viewer_id) for need in needs], total


async def get_need_detail(
    db: AsyncSession,
    need_id: int,
    *,
    viewer_id: int | None = None,
) -> NeedResponse | None:
    result = await db.execute(
        select(Need).options(selectinload(Need.user)).where(Need.id == need_id)
    )
    need = result.unique().scalar_one_or_none()
    if need is None:
        return None
    return await _build_need_response(db, need, viewer_id=viewer_id)


async def update_need(db: AsyncSession, need: Need, data: NeedUpdate) -> NeedResponse:
    if data.title is not None:
        need.title = data.title
    if data.description is not None:
        need.description = data.description
    if data.status is not None:
        need.status = data.status
    await db.commit()
    await db.refresh(need)
    return await _build_need_response(db, need, viewer_id=need.user_id)


async def delete_need(db: AsyncSession, need: Need) -> None:
    await db.execute(delete(Message).where(Message.need_id == need.id))
    await db.execute(delete(Match).where(Match.need_id == need.id))
    await db.execute(delete(NeedApplication).where(NeedApplication.need_id == need.id))
    await db.execute(delete(AgentTask).where(AgentTask.need_id == need.id))
    await db.delete(need)
    await db.commit()


async def select_users(
    db: AsyncSession,
    need: Need,
    data: SelectUsersRequest,
    event_bus: EventBus | None = None,
    *,
    notify_selected: bool = True,
) -> NeedResponse:
    previously_selected = set(need.selected_user_ids or [])

    if need.selection_mode == "single":
        need.selected_user_ids = data.user_ids[:1]
    else:
        existing = set(need.selected_user_ids or [])
        existing.update(data.user_ids)
        need.selected_user_ids = list(existing)

    if need.selection_mode == "single" and need.selected_user_ids:
        need.status = MATCHED_STATUS

    selected_user_ids = list(need.selected_user_ids or [])
    rejected_user_ids: list[int] = []
    rejection_reply = f"需求《{need.title}》已完成匹配，发布者已选择其他候选人。"

    if selected_user_ids:
        await db.execute(
            update(NeedApplication)
            .where(
                NeedApplication.need_id == need.id,
                NeedApplication.applicant_user_id.in_(selected_user_ids),
                NeedApplication.status == "pending",
            )
            .values(status="accepted")
        )
        if need.selection_mode == "single":
            rejected_result = await db.execute(
                select(NeedApplication.applicant_user_id).where(
                    NeedApplication.need_id == need.id,
                    NeedApplication.status == "pending",
                    NeedApplication.applicant_user_id.notin_(selected_user_ids),
                )
            )
            rejected_user_ids = list(rejected_result.scalars().all())
            if rejected_user_ids:
                await db.execute(
                    update(NeedApplication)
                    .where(
                        NeedApplication.need_id == need.id,
                        NeedApplication.applicant_user_id.in_(rejected_user_ids),
                        NeedApplication.status == "pending",
                    )
                    .values(status="rejected", owner_reply=rejection_reply)
                )

    await db.commit()
    await db.refresh(need)

    selected_now = list(need.selected_user_ids or [])
    newly_selected = [user_id for user_id in selected_now if user_id not in previously_selected and user_id != need.user_id]
    if notify_selected and newly_selected:
        owner = need.user or await db.get(User, need.user_id)
        owner_name = owner.username if owner else "发布者"
        content = (
            f"{owner_name} 已选中你参与《{need.title}》。"
            "你可以在这里继续沟通分工和时间；如果暂时不方便参与，也可以直接回复说明。"
        )
        for target_user_id in newly_selected:
            await message_service.send_message(
                db,
                need.user_id,
                MessageCreate(
                    need_id=need.id,
                    receiver_id=target_user_id,
                    content=content,
                ),
                event_bus,
            )

    if rejected_user_ids:
        for target_user_id in rejected_user_ids:
            await message_service.send_message(
                db,
                need.user_id,
                MessageCreate(
                    need_id=need.id,
                    receiver_id=target_user_id,
                    content=rejection_reply,
                ),
                event_bus,
            )

    return await _build_need_response(db, need, viewer_id=need.user_id)


async def deselect_user(db: AsyncSession, need: Need, user_id: int) -> NeedResponse:
    existing = set(need.selected_user_ids or [])
    existing.discard(user_id)
    need.selected_user_ids = list(existing)
    if not need.selected_user_ids and need.status == MATCHED_STATUS:
        need.status = OPEN_STATUS
    await db.commit()
    await db.refresh(need)
    return await _build_need_response(db, need, viewer_id=need.user_id)


async def get_my_needs(db: AsyncSession, user_id: int) -> list[NeedResponse]:
    result = await db.execute(
        select(Need).options(selectinload(Need.user))
        .where(Need.user_id == user_id)
        .order_by(Need.created_at.desc())
    )
    needs = result.unique().scalars().all()
    return [await _build_need_response(db, need, viewer_id=user_id) for need in needs]


async def get_my_selected_needs(db: AsyncSession, user_id: int) -> list[NeedResponse]:
    result = await db.execute(
        select(Need).options(selectinload(Need.user)).order_by(Need.created_at.desc())
    )
    needs = [
        need
        for need in result.unique().scalars().all()
        if need.user_id != user_id and user_id in (need.selected_user_ids or [])
    ]
    return [await _build_need_response(db, need, viewer_id=user_id) for need in needs]
