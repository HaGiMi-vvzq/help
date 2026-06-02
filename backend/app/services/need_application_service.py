from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.models.need import Need
from app.models.need_application import NeedApplication
from app.models.user import User
from app.schemas.message import MessageCreate
from app.schemas.need import NeedApplicationResponse, SelectUsersRequest
from app.services import message_service, need_service

OPEN_STATUS = "\u5f00\u653e"


def _default_application_message(applicant: User, need: Need) -> str:
    skills = ", ".join((applicant.skill_tags or [])[:4]) or "relevant skills"
    return f"Hi, I am interested in {need.title}. I can contribute with {skills} and would love to discuss how to help."


def _default_review_message(need: Need, accepted: bool) -> str:
    if accepted:
        return f"Your application to {need.title} looks promising. Let's continue with task split and timing."
    return f"Thanks for applying to {need.title}. I am moving forward with other candidates for now."


async def _build_response(
    db: AsyncSession,
    application: NeedApplication,
    *,
    need: Need | None = None,
    applicant: User | None = None,
    owner: User | None = None,
) -> NeedApplicationResponse:
    if need is None:
        need = await db.get(Need, application.need_id)
    if applicant is None:
        applicant = await db.get(User, application.applicant_user_id)
    if owner is None and need is not None:
        owner = await db.get(User, need.user_id)

    response = NeedApplicationResponse.model_validate(application)
    response.applicant_username = applicant.username if applicant else ""
    response.applicant_skill_tags = applicant.skill_tags if applicant else []
    response.owner_user_id = owner.id if owner else None
    response.owner_username = owner.username if owner else None
    response.need_title = need.title if need else None
    response.need_status = need.status if need else None
    return response


async def get_my_application(db: AsyncSession, need_id: int, applicant_user_id: int) -> NeedApplication | None:
    result = await db.execute(
        select(NeedApplication)
        .where(
            NeedApplication.need_id == need_id,
            NeedApplication.applicant_user_id == applicant_user_id,
        )
        .order_by(desc(NeedApplication.updated_at), desc(NeedApplication.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_need_applications(db: AsyncSession, need_id: int) -> int:
    result = await db.execute(select(NeedApplication).where(NeedApplication.need_id == need_id))
    return len(result.scalars().all())


async def create_application(
    db: AsyncSession,
    *,
    need: Need,
    applicant: User,
    message: str,
    event_bus: EventBus | None = None,
) -> NeedApplicationResponse:
    if need.user_id == applicant.id:
        raise ValueError("cannot apply to your own need")
    if need.status != OPEN_STATUS:
        raise ValueError("this need is not accepting applications")

    existing = await get_my_application(db, need.id, applicant.id)
    if existing and existing.status in {"pending", "accepted"}:
        raise ValueError("application already exists")

    content = message.strip() or _default_application_message(applicant, need)
    if existing and existing.status in {"rejected", "withdrawn"}:
        existing.message = content
        existing.status = "pending"
        existing.owner_reply = None
        application = existing
    else:
        application = NeedApplication(
            need_id=need.id,
            applicant_user_id=applicant.id,
            message=content,
            status="pending",
        )
        db.add(application)

    await db.commit()
    await db.refresh(application)

    await message_service.send_message(
        db,
        applicant.id,
        MessageCreate(need_id=need.id, receiver_id=need.user_id, content=content),
        event_bus,
    )

    return await _build_response(db, application, need=need, applicant=applicant)


async def list_need_applications(db: AsyncSession, *, need: Need) -> list[NeedApplicationResponse]:
    result = await db.execute(
        select(NeedApplication)
        .where(NeedApplication.need_id == need.id)
        .order_by(desc(NeedApplication.updated_at), desc(NeedApplication.id))
    )
    applications = result.scalars().all()
    owner = await db.get(User, need.user_id)
    return [await _build_response(db, application, need=need, owner=owner) for application in applications]


async def review_application(
    db: AsyncSession,
    *,
    application_id: int,
    owner: User,
    accepted: bool,
    owner_reply: str | None = None,
    event_bus: EventBus | None = None,
) -> NeedApplicationResponse:
    application = await db.get(NeedApplication, application_id)
    if application is None:
        raise ValueError("application not found")

    need = await db.get(Need, application.need_id)
    if need is None:
        raise ValueError("need not found")
    if need.user_id != owner.id:
        raise PermissionError("not allowed to review this application")
    if application.status != "pending":
        raise ValueError("only pending applications can be reviewed")

    application.status = "accepted" if accepted else "rejected"
    application.owner_reply = (owner_reply or "").strip() or _default_review_message(need, accepted)

    if accepted:
        await need_service.select_users(
            db,
            need,
            SelectUsersRequest(user_ids=[application.applicant_user_id]),
            event_bus,
            notify_selected=False,
        )
    else:
        await db.commit()
        await db.refresh(application)

    await message_service.send_message(
        db,
        owner.id,
        MessageCreate(
            need_id=need.id,
            receiver_id=application.applicant_user_id,
            content=application.owner_reply,
        ),
        event_bus,
    )

    await db.refresh(application)
    applicant = await db.get(User, application.applicant_user_id)
    return await _build_response(db, application, need=need, applicant=applicant, owner=owner)


async def list_my_applications(db: AsyncSession, applicant_user_id: int) -> list[NeedApplicationResponse]:
    result = await db.execute(
        select(NeedApplication)
        .where(NeedApplication.applicant_user_id == applicant_user_id)
        .order_by(desc(NeedApplication.updated_at), desc(NeedApplication.id))
    )
    applications = result.scalars().all()
    return [await _build_response(db, application) for application in applications]
