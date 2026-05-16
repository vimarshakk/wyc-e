"""Audit log writer for healthcare compliance trail."""
import uuid
from datetime import datetime, timezone
from .db import audit_logs


async def write_audit(actor_id: str | None, action: str, resource: str,
                      resource_id: str | None = None, meta: dict | None = None):
    await audit_logs.insert_one({
        "audit_id": f"aud_{uuid.uuid4().hex[:16]}",
        "actor_id": actor_id,
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
