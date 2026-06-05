"""Object storage service — MinIO for production, local filesystem for dev."""

import logging
import os
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_minio_client = None
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"


def _get_minio():
    global _minio_client
    if _minio_client is not None:
        return _minio_client

    endpoint = os.getenv("MINIO_ENDPOINT", "")
    if not endpoint:
        return None

    try:
        from minio import Minio
        _minio_client = Minio(
            endpoint,
            access_key=os.getenv("MINIO_ACCESS_KEY", ""),
            secret_key=os.getenv("MINIO_SECRET_KEY", ""),
            secure=False,
        )
        bucket = "avatars"
        if not _minio_client.bucket_exists(bucket):
            _minio_client.make_bucket(bucket)
            logger.info("MinIO bucket '%s' created", bucket)
        return _minio_client
    except Exception as exc:
        logger.warning("MinIO unavailable — using local uploads: %s", exc)
        return None


async def upload_avatar(file_data: bytes, filename: str) -> str:
    """Upload avatar. Returns URL or local path."""
    client = _get_minio()
    ext = os.path.splitext(filename)[1] or ".png"
    object_name = f"avatars/{uuid.uuid4().hex}{ext}"

    if client:
        from minio import S3Error
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.put_object(
                    "avatars", object_name, file_data, len(file_data),
                    content_type=f"image/{ext.lstrip('.')}"
                )
            )
            return f"/api/v1/files/avatars/{object_name}"
        except Exception as exc:
            logger.warning("MinIO upload failed, falling back to local: %s", exc)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    local_path = UPLOAD_DIR / object_name
    local_path.write_bytes(file_data)
    return f"/api/v1/files/local/{object_name}"


async def delete_avatar(url: str) -> None:
    """Delete an uploaded avatar."""
    if "/avatars/" in url or "/local/" in url:
        object_name = url.rsplit("/", 1)[-1]
        client = _get_minio()
        if client:
            try:
                client.remove_object("avatars", object_name)
            except Exception:
                pass
        local_path = UPLOAD_DIR / object_name
        if local_path.exists():
            local_path.unlink()
