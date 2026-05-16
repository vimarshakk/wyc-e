"""Appointments: doctor list, booking, my appointments."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from ...core.db import users, appointments
from ...core.deps import get_current_user
from ...core.audit import write_audit

router = APIRouter(prefix="/appointments", tags=["appointments"])


class BookBody(BaseModel):
    doctor_id: str
    scheduled_at: str  # ISO
    mode: Literal["in_person", "telemedicine"] = "telemedicine"
    reason: Optional[str] = None


@router.get("/doctors")
async def list_doctors(user: dict = Depends(get_current_user)):
    cur = users.find({"role": "doctor"}, {"_id": 0, "password_hash": 0})
    return await cur.to_list(500)


@router.post("")
async def book(body: BookBody, user: dict = Depends(get_current_user)):
    doc = await users.find_one({"user_id": body.doctor_id, "role": "doctor"}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    appt = {
        "appointment_id": f"apt_{uuid.uuid4().hex[:16]}",
        "patient_id": user["user_id"],
        "doctor_id": body.doctor_id,
        "scheduled_at": body.scheduled_at,
        "mode": body.mode,
        "reason": body.reason,
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await appointments.insert_one(appt)
    appt.pop("_id", None)
    await write_audit(user["user_id"], "appointment.book", "appointment", appt["appointment_id"],
                      {"doctor_id": body.doctor_id})
    return appt


@router.get("/mine")
async def my_appointments(user: dict = Depends(get_current_user)):
    query = {"doctor_id": user["user_id"]} if user["role"] == "doctor" else {"patient_id": user["user_id"]}
    cur = appointments.find(query, {"_id": 0}).sort("scheduled_at", -1).limit(200)
    appts = await cur.to_list(200)
    # Enrich with counterpart name
    ids = list({a["doctor_id"] for a in appts} | {a["patient_id"] for a in appts})
    if ids:
        ulist = await users.find({"user_id": {"$in": ids}}, {"_id": 0, "password_hash": 0}).to_list(500)
        umap = {u["user_id"]: u for u in ulist}
        for a in appts:
            a["doctor"] = umap.get(a["doctor_id"])
            a["patient"] = umap.get(a["patient_id"])
    return appts


@router.post("/{apt_id}/cancel")
async def cancel(apt_id: str, user: dict = Depends(get_current_user)):
    a = await appointments.find_one({"appointment_id": apt_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Not found")
    if user["user_id"] not in (a["patient_id"], a["doctor_id"]) and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    await appointments.update_one({"appointment_id": apt_id}, {"$set": {"status": "cancelled"}})
    await write_audit(user["user_id"], "appointment.cancel", "appointment", apt_id)
    return {"ok": True}
