"""Patient care-plan preferences and in-app reminder records."""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.audit import write_audit
from ...core.db import reminder_preferences, reminders
from ...core.deps import get_current_user, require_role

router = APIRouter(prefix="/reminders", tags=["reminders"])


class PreferencesBody(BaseModel):
    in_app: bool = True
    email: bool = False
    sms: bool = False
    whatsapp: bool = False


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    due_at: str
    category: Literal["medication", "follow_up", "lab", "general"] = "general"
    note: Optional[str] = Field(default=None, max_length=300)


@router.get("/preferences")
async def get_preferences(user: dict = Depends(require_role("patient"))):
    preference = await reminder_preferences.find_one({"patient_id": user["user_id"]}, {"_id": 0})
    return preference or {"patient_id": user["user_id"], "in_app": True, "email": False, "sms": False, "whatsapp": False, "external_delivery": "not_configured"}


@router.put("/preferences")
async def save_preferences(body: PreferencesBody, user: dict = Depends(require_role("patient"))):
    preference = {"patient_id": user["user_id"], **body.model_dump(), "external_delivery": "not_configured", "updated_at": datetime.now(timezone.utc).isoformat()}
    await reminder_preferences.update_one({"patient_id": user["user_id"]}, {"$set": preference}, upsert=True)
    await write_audit(user["user_id"], "reminder.preferences.update", "reminder_preferences", user["user_id"])
    return preference


@router.get("/mine")
async def list_reminders(user: dict = Depends(require_role("patient"))):
    return await reminders.find({"patient_id": user["user_id"]}, {"_id": 0}).sort("due_at", 1).to_list(200)


@router.post("")
async def create_reminder(body: ReminderCreate, user: dict = Depends(require_role("patient"))):
    try:
        due_at = datetime.fromisoformat(body.due_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="due_at must be ISO formatted")
    reminder = {"reminder_id": f"rem_{uuid.uuid4().hex[:16]}", "patient_id": user["user_id"], **body.model_dump(), "due_at": due_at.astimezone(timezone.utc).isoformat(), "status": "active", "created_at": datetime.now(timezone.utc).isoformat()}
    await reminders.insert_one(reminder)
    reminder.pop("_id", None)
    await write_audit(user["user_id"], "reminder.create", "reminder", reminder["reminder_id"], {"category": body.category})
    return reminder


@router.post("/{reminder_id}/complete")
async def complete_reminder(reminder_id: str, user: dict = Depends(require_role("patient"))):
    result = await reminders.update_one({"reminder_id": reminder_id, "patient_id": user["user_id"], "status": "active"}, {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}})
    if not result.modified_count:
        raise HTTPException(status_code=404, detail="Active reminder not found")
    await write_audit(user["user_id"], "reminder.complete", "reminder", reminder_id)
    return {"ok": True}