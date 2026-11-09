"""Central minimum-necessary access decisions for clinical resources."""
from datetime import datetime, timezone
from fastapi import HTTPException
from .db import appointments, chart_consents, organization_memberships

PROFESSIONAL_ROLES = {"doctor", "lab", "pharmacy", "insurer", "partner"}

async def require_verified_member(actor: dict) -> None:
    if actor["role"] not in PROFESSIONAL_ROLES:
        return
    if actor.get("verification_status") != "APPROVED":
        raise HTTPException(status_code=403, detail="Account verification is pending")
    membership = await organization_memberships.find_one({"user_id": actor["user_id"], "status": "ACTIVE"}, {"_id": 0, "organization_id": 1})
    if not membership:
        raise HTTPException(status_code=403, detail="Active organization membership is required")

async def can_access_patient_chart(actor: dict, patient_id: str, scope: str = "records") -> bool:
    if actor["user_id"] == patient_id:
        return actor["role"] == "patient"
    if actor["role"] != "doctor":
        return False
    try:
        await require_verified_member(actor)
    except HTTPException:
        return False
    now = datetime.now(timezone.utc).isoformat()
    consent = await chart_consents.find_one({"patient_id": patient_id, "grantee_id": actor["user_id"], "status": "active", "expires_at": {"$gt": now}, "scopes": scope}, {"_id": 0, "consent_id": 1})
    if consent:
        return True
    return bool(await appointments.find_one({"doctor_id": actor["user_id"], "patient_id": patient_id, "status": {"$in": ["scheduled", "completed"]}}, {"_id": 0, "appointment_id": 1}))