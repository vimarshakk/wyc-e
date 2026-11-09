from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import current_user

router = APIRouter(prefix="/availability", tags=["availability"])
_slots: list[dict] = []


class Slot(BaseModel):
    starts_at: datetime
    ends_at: datetime
    mode: str = "VIDEO"


@router.get("")
async def list_slots(provider_id: str | None = None):
    return {"items": [s for s in _slots if not provider_id or s["provider_id"] == provider_id]}


@router.post("")
async def create_slot(payload: Slot, user=Depends(current_user)):
    slot = payload.model_dump() | {"provider_id": user["sub"], "status": "OPEN"}
    _slots.append(slot)
    return slot
