from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.core.deps import require_roles
from app.core.security import create_access_token, hash_password
from app.modules.auth.router import pending_users, set_approval, _users
from uuid import uuid4

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
async def overview(user=Depends(require_roles("ADMIN"))):
    pending = pending_users()
    return {"user": user, "metrics": {"patients": sum(item["role"] == "PATIENT" for item in _users.values()), "providers": sum(item["role"] in {"DOCTOR", "NURSE"} for item in _users.values()), "appointments_today": 0, "pending_reviews": len(pending)}, "pending_signups": pending}


class Decision(BaseModel):
    decision: str


@router.get("/pending-signups")
async def pending_signups(user=Depends(require_roles("ADMIN"))):
    return {"items": pending_users()}


@router.post("/signups/{user_id}/decision")
async def decide_signup(user_id: str, payload: Decision, user=Depends(require_roles("ADMIN"))):
    decision = payload.decision.upper()
    if decision not in {"APPROVED", "REJECTED"}:
        from fastapi import HTTPException
        raise HTTPException(400, "Decision must be APPROVED or REJECTED")
    return await set_approval(user_id, decision, user)


class ProvisionRequest(BaseModel):
    email: EmailStr
    name: str = ""
    role: str = Field(pattern="^(DOCTOR|NURSE|LAB|PHARMACY|INSURER|PARTNER)$")
    temporary_password: str = Field(min_length=8)


@router.post("/provision")
async def provision(payload: ProvisionRequest, user=Depends(require_roles("ADMIN"))):
    email = payload.email.lower()
    if email in _users:
        from fastapi import HTTPException
        raise HTTPException(409, "Account already exists")
    account = {"id": str(uuid4()), "email": email, "name": payload.name, "role": payload.role, "approval_status": "APPROVED", "password_hash": hash_password(payload.temporary_password), "provisioned_by": user["sub"]}
    _users[email] = account
    return {"user": {k: account[k] for k in ("id", "email", "name", "role", "approval_status")}, "access_token": create_access_token(account["id"], account["role"])}
