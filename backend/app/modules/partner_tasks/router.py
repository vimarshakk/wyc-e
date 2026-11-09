import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.db import partner_tasks, users
from ...core.deps import get_current_user, require_role

router = APIRouter(prefix="/partner-tasks", tags=["partner-tasks"])
class TaskBody(BaseModel):
    partner_id: str
    patient_id: str
    task_type: str = Field(pattern="^(lab_order|pharmacy_fulfilment|claim_review|integration_task)$")

@router.get("/mine")
async def mine(user: dict = Depends(get_current_user)):
    if user["role"] not in ("lab", "pharmacy", "insurer", "partner"): raise HTTPException(status_code=403, detail="Partner role required")
    if user.get("verification_status") != "APPROVED": return []
    return await partner_tasks.find({"partner_id": user["user_id"], "status": "CONSENT_GRANTED"}, {"_id": 0, "patient_id": 0}).to_list(200)

@router.post("")
async def create(body: TaskBody, user: dict = Depends(require_role("doctor", "admin"))):
    partner = await users.find_one({"user_id": body.partner_id}, {"_id": 0, "role": 1, "verification_status": 1})
    if not partner or partner.get("verification_status") != "APPROVED": raise HTTPException(status_code=409, detail="Partner must be approved")
    task = {"task_id": f"pt_{uuid.uuid4().hex[:16]}", "partner_id": body.partner_id, "patient_id": body.patient_id, "task_type": body.task_type, "status": "CONSENT_REQUIRED", "created_by": user["user_id"], "created_at": datetime.now(timezone.utc).isoformat()}
    await partner_tasks.insert_one(task); task.pop("_id", None); task.pop("patient_id", None)
    return task