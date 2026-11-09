from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import current_user

router = APIRouter(prefix="/appointments", tags=["appointments"])
_appointments: list[dict] = []


class Appointment(BaseModel):
    provider_id: str
    starts_at: datetime
    mode: str = "VIDEO"
    reason: str = ""


@router.get("")
async def list_appointments(user=Depends(current_user)):
    return {"items": [a for a in _appointments if a["patient_id"] == user["sub"] or a["provider_id"] == user["sub"]]}


@router.post("")
async def book_appointment(payload: Appointment, user=Depends(current_user)):
    item = payload.model_dump() | {"patient_id": user["sub"], "status": "REQUESTED"}
    _appointments.append(item)
    return item
