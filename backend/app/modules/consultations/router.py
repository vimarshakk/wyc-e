from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import current_user, require_roles

router = APIRouter(prefix="/consultations", tags=["consultations"])
_consultations: list[dict] = []


class Note(BaseModel):
    patient_id: str
    summary: str
    plan: str = ""


@router.post("")
async def create_note(payload: Note, user=Depends(require_roles("DOCTOR", "NURSE"))):
    item = payload.model_dump() | {"provider_id": user["sub"], "created_at": datetime.now(timezone.utc).isoformat()}
    _consultations.append(item)
    return item


@router.get("/{patient_id}")
async def patient_notes(patient_id: str, user=Depends(current_user)):
    return {"items": [n for n in _consultations if n["patient_id"] == patient_id or user["sub"] == patient_id]}
