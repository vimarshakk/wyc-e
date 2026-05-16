"""Emergent object storage abstraction."""
import requests
import logging
from ...core.config import settings

logger = logging.getLogger(__name__)
_storage_key: str | None = None


def init_storage() -> str | None:
    global _storage_key
    if _storage_key:
        return _storage_key
    if not settings.EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY missing; storage disabled")
        return None
    try:
        resp = requests.post(
            f"{settings.STORAGE_URL}/init",
            json={"emergent_key": settings.EMERGENT_LLM_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        return _storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise RuntimeError("Storage not initialized")
    resp = requests.put(
        f"{settings.STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple[bytes, str]:
    key = init_storage()
    if not key:
        raise RuntimeError("Storage not initialized")
    resp = requests.get(
        f"{settings.STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
