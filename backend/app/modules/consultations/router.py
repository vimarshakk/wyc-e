"""Telemedicine consultation workspace and clinical-note lifecycle."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.audit import write_audit
from ...core.db import appointments, consultation_notes, consultations, users
from ...core.deps import get_current_user, require_role

router = APIRouter(prefix="/consultations", tags=["consultations"])


class NoteBody(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


async def _consultation_for_user(consultation_id: str, user: dict) -> dict:
    consultation = await consultations.find_one({"consultation_id": consultation_id}, {"_id": 0})
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    if user["user_id"] not in (consultation["patient_id"], consultation["doctor_id"]) and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    return consultation


@router.post("/from-appointment/{appointment_id}")
async def create_from_appointment(appointment_id: str, user: dict = Depends(get_current_user)):
    appointment = await appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.get("mode") != "telemedicine" or appointment.get("status") != "scheduled":
        raise HTTPException(status_code=409, detail="A scheduled telemedicine appointment is required")
    if user["user_id"] not in (appointment["patient_id"], appointment["doctor_id"]):
        raise HTTPException(status_code=403, detail="Not allowed")
    existing = await consultations.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if existing:
        return existing
    consultation = {
        "consultation_id": f"con_{uuid.uuid4().hex[:16]}",
        "appointment_id": appointment_id,
        "patient_id": appointment["patient_id"],
        "doctor_id": appointment["doctor_id"],
        "scheduled_at": appointment["scheduled_at"],
        "room_name": f"room_{uuid.uuid4().hex}",
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await consultations.insert_one(consultation)
    except Exception:
        existing = await consultations.find_one({"appointment_id": appointment_id}, {"_id": 0})
        if existing:
            return existing
        raise
    consultation.pop("_id", None)
    await write_audit(user["user_id"], "consultation.create", "consultation", consultation["consultation_id"], {"appointment_id": appointment_id})
    return consultation


@router.get("/mine")
async def list_mine(user: dict = Depends(get_current_user)):
    query = {} if user["role"] == "admin" else ({"doctor_id": user["user_id"]} if user["role"] == "doctor" else {"patient_id": user["user_id"]})
    items = await consultations.find(query, {"_id": 0}).sort("scheduled_at", -1).to_list(200)
    counterpart_ids = list({item["patient_id"] if user["role"] == "doctor" else item["doctor_id"] for item in items})
    people = await users.find({"user_id": {"$in": counterpart_ids}}, {"_id": 0, "password_hash": 0}).to_list(200) if counterpart_ids else []
    person_map = {person["user_id"]: person for person in people}
    for item in items:
        item["counterpart"] = person_map.get(item["patient_id"] if user["role"] == "doctor" else item["doctor_id"])
    return items


@router.get("/{consultation_id}")
async def get_consultation(consultation_id: str, user: dict = Depends(get_current_user)):
    consultation = await _consultation_for_user(consultation_id, user)
    notes = await consultation_notes.find({"consultation_id": consultation_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    appointment = await appointments.find_one({"appointment_id": consultation["appointment_id"]}, {"_id": 0, "video_link_status": 1})
    return {**consultation, "video_link_status": appointment.get("video_link_status", "preparing") if appointment else "preparing", "notes": notes}


@router.post("/{consultation_id}/join")
async def join_consultation(consultation_id: str, user: dict = Depends(get_current_user)):
    consultation = await _consultation_for_user(consultation_id, user)
    if consultation["status"] == "completed":
        raise HTTPException(status_code=409, detail="Consultation is completed")
    appointment = await appointments.find_one({"appointment_id": consultation["appointment_id"]}, {"_id": 0, "meeting_url": 1, "video_link_status": 1})
    if not appointment or appointment.get("video_link_status") != "ready" or not appointment.get("meeting_url"):
        raise HTTPException(status_code=409, detail="Preparing video link")
    await consultations.update_one({"consultation_id": consultation_id, "status": "ready"}, {"$set": {"status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}})
    await write_audit(user["user_id"], "consultation.join", "consultation", consultation_id)
    return {"meeting_url": appointment["meeting_url"], "video_link_status": "ready"}


@router.post("/{consultation_id}/notes")
async def save_note(consultation_id: str, body: NoteBody, user: dict = Depends(require_role("doctor"))):
    consultation = await _consultation_for_user(consultation_id, user)
    if consultation["doctor_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    if consultation["status"] == "completed":
        raise HTTPException(status_code=409, detail="Consultation is completed")
    note = {"note_id": f"note_{uuid.uuid4().hex[:16]}", "consultation_id": consultation_id, "author_id": user["user_id"], "content": body.content, "created_at": datetime.now(timezone.utc).isoformat()}
    await consultation_notes.insert_one(note)
    note.pop("_id", None)
    await write_audit(user["user_id"], "consultation.note.create", "consultation", consultation_id)
    return note


@router.post("/{consultation_id}/complete")
async def complete_consultation(consultation_id: str, user: dict = Depends(require_role("doctor"))):
    consultation = await _consultation_for_user(consultation_id, user)
    if consultation["doctor_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not allowed")
    await consultations.update_one({"consultation_id": consultation_id}, {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}})
    await appointments.update_one({"appointment_id": consultation["appointment_id"]}, {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}})
    await write_audit(user["user_id"], "consultation.complete", "consultation", consultation_id)
    return {"ok": True}