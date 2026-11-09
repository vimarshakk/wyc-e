from uuid import uuid4

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.security import create_access_token, hash_password, verify_password
from app.core.deps import current_user
from app.core.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])
_users: dict[str, dict] = {}
APPROVAL_ROLES = {"DOCTOR", "NURSE", "LAB", "PHARMACY", "INSURER", "PARTNER"}
PUBLIC_ROLES = {"PATIENT", *APPROVAL_ROLES}


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "PATIENT"
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
async def signup(payload: SignupRequest):
    email = payload.email.lower()
    role = payload.role.upper()
    if role not in PUBLIC_ROLES:
        raise HTTPException(400, "This account type is not available for public signup")
    if email in _users:
        raise HTTPException(409, "Account already exists")
    approval_status = "PENDING_APPROVAL" if role in APPROVAL_ROLES else "APPROVED"
    user = {"id": str(uuid4()), "email": email, "name": payload.name, "role": role, "approval_status": approval_status, "password_hash": hash_password(payload.password), "created_at": datetime.now(timezone.utc).isoformat()}
    _users[email] = user
    public_user = {k: user[k] for k in ("id", "email", "name", "role", "approval_status")}
    if approval_status == "PENDING_APPROVAL":
        return {"user": public_user, "status": approval_status, "message": "Signup received. An administrator must approve this account before workspace access."}
    return {"user": public_user, "status": approval_status, "access_token": create_access_token(user["id"], user["role"])}


@router.post("/login")
async def login(payload: LoginRequest):
    user = _users.get(payload.email.lower())
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    if user["approval_status"] != "APPROVED":
        raise HTTPException(403, {"code": "ACCOUNT_PENDING_APPROVAL", "message": "Your signup is awaiting administrator approval.", "approval_status": user["approval_status"]})
    return {"user": {k: user[k] for k in ("id", "email", "name", "role", "approval_status")}, "access_token": create_access_token(user["id"], user["role"])}


@router.get("/me")
async def me(user=Depends(current_user)):
    return {"user": user}


def pending_users() -> list[dict]:
    return [{k: user[k] for k in ("id", "email", "name", "role", "approval_status", "created_at")} for user in _users.values() if user["approval_status"] == "PENDING_APPROVAL"]


async def set_approval(user_id: str, approval_status: str, actor: dict) -> dict:
    user = next((item for item in _users.values() if item["id"] == user_id), None)
    if not user:
        raise HTTPException(404, "Signup not found")
    user["approval_status"] = approval_status
    user["approved_by"] = actor["sub"]
    user["approved_at"] = datetime.now(timezone.utc).isoformat()
    await record_audit(actor["sub"], f"ACCOUNT_{approval_status}", user_id, {"role": user["role"]})
    return {k: user[k] for k in ("id", "email", "name", "role", "approval_status")}
