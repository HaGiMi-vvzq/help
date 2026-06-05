import asyncio
import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import settings as app_settings, is_postgres, is_sqlite
from app.core.database import Base, engine, async_session, backup_db, migrate_sqlite_schema
from app.core.events import get_event_bus
from app.knowledge.skill_graph import get_skill_graph

# Import prompt templates to trigger registration
import app.prompts.tag_extraction  # noqa: F401
import app.prompts.rerank  # noqa: F401
import app.prompts.need_refinement  # noqa: F401
import app.prompts.need_writing  # noqa: F401
import app.prompts.file_analyzer  # noqa: F401
import app.prompts.agent_intent  # noqa: F401
import app.prompts.agent_planner  # noqa: F401
import app.prompts.semantic_router  # noqa: F401

# Import skills to trigger registration
from app.skills.registry import SkillRegistry
from app.skills.tag_skill import TagSkill
from app.skills.embed_skill import EmbedSkill
from app.skills.match_skill import MatchSkill
from app.skills.explain_skill import ExplainSkill
from app.skills.moderate_skill import ModerateSkill
from app.skills.file_reader import FileReaderSkill
from app.skills.task_planner import TaskPlannerSkill
from app.skills.context_summarizer import ContextSummarizerSkill
from app.skills.semantic_router import SemanticRouterSkill

from app.routers import auth, profile, needs, messages, agents, settings, admin


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exc"] = str(record.exc_info[1])
        return json.dumps(entry, ensure_ascii=False)


def _setup_logging():
    level = getattr(logging, app_settings.LOG_LEVEL.upper(), logging.INFO)
    fmt = JsonFormatter() if not app_settings.DEBUG else logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    # Console handler (stderr)
    console_handler: logging.Handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(level)
    root.addHandler(console_handler)

    # File handler with rotation (always enabled for production audit)
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    root.addHandler(file_handler)


_setup_logging()
logger = logging.getLogger(__name__)


def register_skills():
    SkillRegistry.register(TagSkill())
    SkillRegistry.register(EmbedSkill())
    SkillRegistry.register(MatchSkill())
    SkillRegistry.register(ExplainSkill())
    SkillRegistry.register(ModerateSkill())
    SkillRegistry.register(FileReaderSkill())
    SkillRegistry.register(TaskPlannerSkill())
    SkillRegistry.register(ContextSummarizerSkill())
    SkillRegistry.register(SemanticRouterSkill())
    logger.info("Registered %d skills", len(SkillRegistry.list_all()))


def register_event_handlers():
    bus = get_event_bus()

    async def on_user_registered(event: str, data: dict):
        logger.info("[Event] user_registered: user_id=%s", data.get("user_id"))
        from app.models.behavior import UserPreferenceProfile
        async with async_session() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(UserPreferenceProfile).where(UserPreferenceProfile.user_id == data["user_id"])
            )
            if not result.scalar_one_or_none():
                db.add(UserPreferenceProfile(user_id=data["user_id"]))
                await db.commit()

    async def on_feedback(event: str, data: dict):
        logger.info("[Event] feedback: %s", data)
        from app.services.reflection_service import check_and_reflect
        async with async_session() as db:
            await check_and_reflect(db, data.get("user_id", 0))

    async def on_need_published(event: str, data: dict):
        logger.info("[Event] need_published: %s", data)

    bus.on("user_registered", on_user_registered)
    bus.on("feedback_received", on_feedback)
    bus.on("need_published", on_need_published)

    async def on_agent_file_processed(event: str, data: dict):
        logger.info("[Event] agent_file_processed: %s", data.get("filename"))

    async def on_agent_need_created(event: str, data: dict):
        logger.info("[Event] agent_need_created: need_id=%s", data.get("need_id"))

    async def on_agent_match_completed(event: str, data: dict):
        logger.info("[Event] agent_match_completed: session=%s, need=%s, count=%s",
                    data.get("session_id"), data.get("need_id"), data.get("match_count"))

    bus.on("agent_file_processed", on_agent_file_processed)
    bus.on("agent_need_created", on_agent_need_created)
    bus.on("agent_match_completed", on_agent_match_completed)
    logger.info("Registered event handlers")


def create_app() -> FastAPI:
    register_skills()
    register_event_handlers()

    cors_origins = [o.strip() for o in app_settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    app = FastAPI(
        title="Campus AI Match",
        docs_url="/docs" if app_settings.DEBUG else None,
        redoc_url=None,
    )

    app.add_middleware(GZipMiddleware, minimum_size=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Global exception handlers ──────────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        logger.warning("HTTP %d on %s %s: %s", exc.status_code, request.method, request.url.path, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "request_error", "detail": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exc(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        detail = errors[0].get("msg", "invalid request") if errors else "invalid request"
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, detail)
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": detail},
        )

    @app.exception_handler(Exception)
    async def catchall_exc(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": "an unexpected error occurred"},
        )

    @app.middleware("http")
    async def behavior_log_middleware(request: Request, call_next):
        """自动记录 API 行为日志：注册、发需求、查看匹配、发消息。"""
        start = time.time()
        response: Response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        path = request.url.path
        method = request.method

        # Exact match first, then suffix patterns
        event = None
        for (m, p), e in [
            (("POST", "/api/v1/auth/register"), "register"),
            (("POST", "/api/v1/needs"), "publish_need"),
            (("POST", "/api/v1/messages"), "send_message"),
        ]:
            if method == m and path == p:
                event = e
                break

        if not event:
            if method == "GET" and "/matches" in path:
                event = "view_matches"
            elif method == "POST" and path.endswith("/feedback"):
                event = "feedback"

        if event and response.status_code < 400:
            # Log as background task so it doesn't block the response
            async def log_bg():
                try:
                    from app.models.behavior import UserBehaviorLog

                    user_id = None
                    auth_header = request.headers.get("Authorization", "")
                    if auth_header.startswith("Bearer "):
                        from app.core.security import decode_access_token
                        payload = decode_access_token(auth_header[7:])
                        if payload:
                            user_id = payload.get("user_id")

                    if user_id:
                        async with async_session() as db:
                            log = UserBehaviorLog(
                                user_id=user_id,
                                event_type=event,
                                extra_data={"path": path, "duration_ms": round(duration_ms)},
                            )
                            db.add(log)
                            await db.commit()
                except Exception:
                    logger.debug("Behavior log skipped: %s", method, exc_info=True)

            asyncio.create_task(log_bg())

        return response

    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(needs.router)
    app.include_router(messages.router)
    app.include_router(agents.router)
    app.include_router(settings.router)
    app.include_router(admin.router)

    # ── File serving for avatars (MinIO proxy) ──
    from fastapi.responses import FileResponse, Response
    import mimetypes

    @app.get("/api/v1/files/{storage}/{path:path}")
    async def serve_file(storage: str, path: str):
        if storage == "local":
            file_path = os.path.join(BASE_DIR, "..", "uploads", path)
            if os.path.isfile(file_path):
                mime, _ = mimetypes.guess_type(file_path)
                return FileResponse(file_path, media_type=mime or "application/octet-stream")
        elif storage == "avatars":
            try:
                from minio import Minio
                client = Minio(
                    os.getenv("MINIO_ENDPOINT", "minio:9000"),
                    access_key=os.getenv("MINIO_ACCESS_KEY", ""),
                    secret_key=os.getenv("MINIO_SECRET_KEY", ""),
                    secure=False,
                )
                data = client.get_object("avatars", path)
                mime, _ = mimetypes.guess_type(path)
                return Response(content=data.read(), media_type=mime or "image/png")
            except Exception:
                pass
        raise HTTPException(404, "File not found")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    GRAPH_PATH = os.path.join(BASE_DIR, "..", "skill_graph.json")

    @app.on_event("startup")
    async def startup():
        # Refuse to start if SECRET_KEY is not configured
        if not app_settings.SECRET_KEY:
            logger.critical(
                "SECRET_KEY is not configured. Set it in backend/.env or via environment variable. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
            sys.exit(1)

        # Sentry
        if app_settings.SENTRY_DSN:
            import sentry_sdk
            sentry_sdk.init(
                dsn=app_settings.SENTRY_DSN,
                traces_sample_rate=0.1,
                environment="production" if not app_settings.DEBUG else "development",
            )
            logger.info("Sentry initialized")

        # Logs directory
        logs_dir = os.path.join(BASE_DIR, "..", "logs")
        os.makedirs(logs_dir, exist_ok=True)

        backup_db()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await migrate_sqlite_schema(conn)

        # Redis (best-effort)
        try:
            from app.core.redis import get_redis
            await get_redis()
        except Exception:
            logger.info("Redis not available — running without cache")

        graph = get_skill_graph()
        graph.from_file(GRAPH_PATH)
        logger.info("App started, DB ready (%s), graph loaded (%d edges)",
                    "postgres" if is_postgres() else "sqlite" if is_sqlite() else "unknown",
                    len(graph))

    @app.on_event("shutdown")
    async def shutdown():
        get_skill_graph().to_file(GRAPH_PATH)
        try:
            from app.core.redis import close_redis
            await close_redis()
        except Exception:
            pass
        try:
            from app.integrations.client import AIClient
            await AIClient.close_http()
        except Exception:
            pass
        await engine.dispose()

    @app.get("/api/v1/skills")
    async def list_skills():
        return SkillRegistry.list_all()

    @app.get("/api/v1/health")
    @app.get("/api/health")  # backward compat
    async def health():
        checks: dict = {"db": "ok"}

        # Redis check
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            await r.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"

        # DeepSeek connectivity check
        try:
            from app.integrations.client import get_ai_client
            client = get_ai_client()
            if not client.api_key or client.api_key.startswith("sk-your-"):
                checks["deepseek"] = "unconfigured"
            else:
                checks["deepseek"] = "configured"
        except Exception:
            checks["deepseek"] = "error"

        # Qwen model check
        try:
            from app.adapters.qwen_adapter import Qwen3EmbedAdapter
            embed = Qwen3EmbedAdapter()
            if embed.model is not None:
                checks["qwen_embed"] = "loaded"
            else:
                checks["qwen_embed"] = "not_loaded"
        except Exception:
            checks["qwen_embed"] = "not_loaded"

        all_ok = checks.get("db") == "ok"
        return {"status": "ok" if all_ok else "degraded", "checks": checks}

    return app


app = create_app()
