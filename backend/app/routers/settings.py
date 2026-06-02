"""System settings API for runtime AI provider configuration."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select as _s
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_DIR
from app.core.database import get_db
from app.core.deps import get_current_user
from app.integrations.client import AIClient, apply_runtime_config
from app.models.system_config import SystemConfig
from app.models.user import User

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    deepseek_api_key: str = ""


class SettingsApiKeyCheck(BaseModel):
    deepseek_api_key: str = ""


def validate_api_key_format(key: str) -> None:
    if key and not key.startswith("sk-"):
        raise HTTPException(400, "API Key 格式不正确，应以 sk- 开头")
    if "\n" in key or "\r" in key:
        raise HTTPException(400, "API Key 不能包含换行符")


@router.get("")
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(_s(SystemConfig))
    configs = {c.key: c.value for c in r.scalars().all()}
    key = configs.get("deepseek_api_key", "")
    has_key = bool(key)
    masked = key[:7] + "***" + key[-4:] if len(key) > 10 else ("***" if key else "")
    return {
        "has_api_key": has_key,
        "api_key_masked": masked,
        "base_url": configs.get("deepseek_base_url", "https://api.deepseek.com"),
        "pro_model": configs.get("deepseek_pro_model", "deepseek-v4-pro"),
        "flash_model": configs.get("deepseek_flash_model", "deepseek-v4-flash"),
    }


@router.put("")
async def update_settings(
    data: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = data.deepseek_api_key.strip()
    validate_api_key_format(key)

    if key:
        await _upsert(db, "deepseek_api_key", key)
        persist_env_value("DEEPSEEK_API_KEY", key)
        apply_runtime_config(deepseek_api_key=key)
    return {"ok": True, "message": "设置已保存并立即生效"}


@router.post("/test-api-key")
async def test_api_key(
    data: SettingsApiKeyCheck,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = data.deepseek_api_key.strip()
    if not key:
        raise HTTPException(400, "请输入 API Key")
    validate_api_key_format(key)

    base_url = await get_config_value(db, "deepseek_base_url", "https://api.deepseek.com")
    flash_model = await get_config_value(db, "deepseek_flash_model", "deepseek-v4-flash")
    client = AIClient(api_key=key, base_url=base_url, flash_model=flash_model)
    try:
        await client.chat(
            [{"role": "user", "content": "请只回复 ok，用于检测 API Key 是否可用。"}],
            model=flash_model,
            temperature=0,
            max_tokens=8,
            timeout=8,
            max_retries=0,
        )
        path_text = "本地代理" if client.last_connection_path == "local_proxy" else "默认网络"
        return {
            "ok": True,
            "message": f"API Key 可用，当前通过{path_text}连接 DeepSeek",
            "connection_path": client.last_connection_path,
        }
    except Exception as exc:
        return {"ok": False, "message": explain_api_check_error(exc), "connection_path": client.last_connection_path}


def explain_api_check_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "api error 401" in lowered or "api error 403" in lowered:
        return "API Key 无效或没有访问权限"
    if "api error 402" in lowered:
        return "账户余额不足或额度受限"
    if "timed out" in lowered or "timeout" in lowered:
        return "检测超时，请检查网络或稍后重试"
    if "connect" in lowered or "connection" in lowered:
        return "默认网络和本地代理都无法连接 DeepSeek，请检查网络、代理或 API 地址"
    if "api error 400" in lowered:
        return "请求被模型服务拒绝，请检查模型配置"
    return f"检测失败：{message[:120]}"


@router.get("/status")
async def api_status():
    """Public endpoint for checking whether an API key is configured."""
    from app.core.database import async_session

    async with async_session() as db:
        r = await db.execute(_s(SystemConfig))
        configs = {c.key: c.value for c in r.scalars().all()}
        has_key = bool(configs.get("deepseek_api_key", ""))
    return {"configured": has_key}


async def _upsert(db: AsyncSession, key: str, value: str):
    r = await db.execute(_s(SystemConfig).where(SystemConfig.key == key))
    existing = r.scalar_one_or_none()
    if existing:
        existing.value = value
    else:
        db.add(SystemConfig(key=key, value=value))
    await db.commit()


def persist_env_value(key: str, value: str, env_path: str | Path | None = None) -> None:
    path = Path(env_path) if env_path is not None else BACKEND_DIR / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    prefix = f"{key}="
    updated: list[str] = []
    replaced = False

    for line in lines:
        if line.startswith(prefix):
            updated.append(f"{key}={value}")
            replaced = True
        else:
            updated.append(line)

    if not replaced:
        updated.append(f"{key}={value}")

    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


async def get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    r = await db.execute(_s(SystemConfig).where(SystemConfig.key == key))
    c = r.scalar_one_or_none()
    return c.value if c else default
