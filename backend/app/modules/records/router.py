"""EMR / Health records endpoints."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from ...core.db import appointments, consultations, lab_reports, prescriptions, records
from ...core.deps import get_current_user
from ...core.audit import write_audit

router = APIRouter(prefix="/records", tags=["records"])

RecordType = Literal["prescription", "lab_report", "imaging", "vitals", "note"]


class RecordCreate(BaseModel):
    title: str
    record_type: RecordType
    summary: Optional[str] = None
    file_id: Optional[str] = None
    data: Optional[dict] = None
    patient_id: Optional[str] = None  # doctors/admins can specify; patients use their own


@router.post("")
async def create_record(body: RecordCreate, user: dict = Depends(get_current_user)):
    target_patient = body.patient_id or user["user_id"]
    if target_patient != user["user_id"] and user["role"] not in ("doctor", "admin"):
        raise HTTPException(status_code=403, detail="Not allowed")
    rec = {
        "record_id": f"rec_{uuid.uuid4().hex[:16]}",
        "patient_id": target_patient,
        "author_id": user["user_id"],
        "record_type": body.record_type,
        "title": body.title,
        "summary": body.summary,
        "file_id": body.file_id,
        "data": body.data or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await records.insert_one(rec)
    rec.pop("_id", None)
    await write_audit(user["user_id"], "record.create", "record", rec["record_id"],
                      {"patient": target_patient, "type": body.record_type})
    return rec


@router.get("")
async def list_records(patient_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    target = patient_id or user["user_id"]
    if target != user["user_id"] and user["role"] not in ("doctor", "admin"):
        raise HTTPException(status_code=403, detail="Not allowed")
    cur = records.find({"patient_id": target}, {"_id": 0}).sort("created_at", -1).limit(500)
    return await cur.to_list(500)


@router.get("/timeline")
async def timeline(user: dict = Depends(get_current_user)):
    """Longitudinal merged timeline of reviewed records and care activity."""
    pid = user["user_id"]
    recs = await records.find({"patient_id": pid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    pres = await prescriptions.find({"patient_id": pid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    labs = await lab_reports.find({"patient_id": pid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    appts = await appointments.find({"patient_id": pid}, {"_id": 0}).sort("scheduled_at", -1).limit(200).to_list(200)
    sessions = await consultations.find({"patient_id": pid}, {"_id": 0}).sort("scheduled_at", -1).limit(200).to_list(200)
    events: List[dict] = []
    for r in recs:
        events.append({
            "kind": r["record_type"],
            "id": r["record_id"],
            "title": r["title"],
            "summary": r.get("summary"),
            "created_at": r["created_at"],
        })
    for p in pres:
        meds = p.get("extracted", {}).get("medications", [])
        events.append({
            "kind": "prescription_ocr",
            "id": p["prescription_id"],
            "title": p.get("extracted", {}).get("doctor_name") or "Prescription",
            "summary": f"{len(meds)} medication(s) extracted",
            "created_at": p["created_at"],
        })
    for lab in labs:
        observations = lab.get("extracted", {}).get("observations", [])
        events.append({"kind": "lab_report", "id": lab["document_id"], "title": lab.get("extracted", {}).get("lab_name") or "Lab report", "summary": f"{len(observations)} observation(s) extracted · {lab.get('review_state', 'pending')}", "created_at": lab["created_at"]})
    for appointment in appts:
        events.append({"kind": "appointment", "id": appointment["appointment_id"], "title": "Teleconsultation" if appointment.get("mode") == "telemedicine" else "Clinic appointment", "summary": appointment.get("status", "scheduled"), "created_at": appointment["scheduled_at"]})
    for session in sessions:
        events.append({"kind": "consultation", "id": session["consultation_id"], "title": "Clinical consultation", "summary": session.get("status", "ready"), "created_at": session["scheduled_at"]})
    events.sort(key=lambda e: e["created_at"], reverse=True)
    return events
