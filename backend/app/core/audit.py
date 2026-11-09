from datetime import datetime, timezone

from .db import collection


async def record_audit(actor_id: str, action: str, resource: str, metadata: dict | None = None) -> None:
    event = {"actor_id": actor_id, "action": action, "resource": resource, "metadata": metadata or {}, "created_at": datetime.now(timezone.utc)}
    events = collection("audit_events")
    if events is not None:
        await events.insert_one(event)
