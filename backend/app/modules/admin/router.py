"""Admin endpoints: stats, audit logs, user list."""
from fastapi import APIRouter, Depends
from ...core.db import users, prescriptions, appointments, audit_logs, wysh_ids
from ...core.deps import require_role

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


@router.get("/stats")
async def stats():
    return {
        "users_total": await users.count_documents({}),
        "patients": await users.count_documents({"role": "patient"}),
        "doctors": await users.count_documents({"role": "doctor"}),
        "wysh_ids_verified": await wysh_ids.count_documents({"verification_status": "verified"}),
        "prescriptions_ocr": await prescriptions.count_documents({}),
        "appointments_scheduled": await appointments.count_documents({"status": "scheduled"}),
    }


@router.get("/users")
async def list_users():
    cur = users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(500)
    return await cur.to_list(500)


@router.get("/audit")
async def audit(limit: int = 100):
    cur = audit_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cur.to_list(limit)
