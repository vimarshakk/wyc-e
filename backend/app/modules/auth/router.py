"""Auth: signup, login (JWT), Google OAuth session exchange, me, logout."""
import uuid
import requests
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Response, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
from ...core.config import settings
from ...core.db import users, sessions, wysh_ids
from ...core.security import hash_password, verify_password, create_jwt
from ...core.deps import get_current_user, require_role
from ...core.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])

ROLES = ("patient", "doctor", "admin", "lab", "pharmacy", "insurer", "partner")


def _gen_wysh_id() -> str:
    """Format: WYSH-XXXX-XXXX (human-readable verified health identity)."""
    a = uuid.uuid4().hex[:4].upper()
    b = uuid.uuid4().hex[:4].upper()
    return f"WYSH-{a}-{b}"


async def _create_wysh_id(user_id: str, role: str) -> str:
    wid = _gen_wysh_id()
    while await wysh_ids.find_one({"wysh_id": wid}):
        wid = _gen_wysh_id()
    await wysh_ids.insert_one({
        "wysh_id": wid,
        "user_id": user_id,
        "role": role,
        "verification_status": "verified" if role == "admin" else "pending",
        "trust_score": 50,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return wid


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=2)
    role: Literal["patient", "doctor", "admin", "lab", "pharmacy", "insurer", "partner"] = "patient"
    phone: Optional[str] = None
    specialty: Optional[str] = None  # for doctors
    organization_name: Optional[str] = Field(default=None, max_length=160)
    registration_number: Optional[str] = Field(default=None, max_length=120)
    registration_jurisdiction: Optional[str] = Field(default=None, max_length=120)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class GoogleExchangeBody(BaseModel):
    session_id: str


class PartnerProvisionBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    name: str = Field(min_length=2, max_length=120)
    role: Literal["lab", "pharmacy", "insurer", "partner"]
    organization_name: str = Field(min_length=2, max_length=160)


@router.post("/signup")
async def signup(body: SignupBody):
    if body.role != "patient" and (not body.organization_name or not body.registration_number):
        raise HTTPException(status_code=400, detail="Organization and registration number are required for professional accounts")
    existing = await users.find_one({"email": body.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = f"usr_{uuid.uuid4().hex[:16]}"
    wysh_id = await _create_wysh_id(user_id, body.role)
    doc = {
        "user_id": user_id,
        "email": body.email,
        "name": body.name,
        "role": body.role,
        "phone": body.phone,
        "specialty": body.specialty,
        "organization_name": body.organization_name,
        "registration_number": body.registration_number,
        "registration_jurisdiction": body.registration_jurisdiction,
        "verification_status": "APPROVED" if body.role == "patient" else "VERIFICATION_PENDING",
        "verification_source": "self_declared" if body.role != "patient" else "patient_otp_pending",
        "wysh_id": wysh_id,
        "password_hash": hash_password(body.password),
        "auth_provider": "password",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await users.insert_one(doc)
    doc.pop("_id", None)
    await write_audit(user_id, "user.signup", "user", user_id, {"role": body.role})
    token = create_jwt(user_id, body.role)
    return {
        "token": token,
        "user": {k: v for k, v in doc.items() if k != "password_hash"},
    }


@router.post("/login")
async def login(body: LoginBody):
    user = await users.find_one({"email": body.email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt(user["user_id"], user["role"])
    await write_audit(user["user_id"], "user.login", "user", user["user_id"])
    user.pop("password_hash", None)
    return {"token": token, "user": user}


@router.post("/partners", status_code=201)
async def provision_partner(body: PartnerProvisionBody, user: dict = Depends(require_role("admin"))):
    if await users.find_one({"email": body.email}, {"_id": 0, "user_id": 1}):
        raise HTTPException(status_code=409, detail="Email already registered")
    user_id = f"usr_{uuid.uuid4().hex[:16]}"
    wysh_id = await _create_wysh_id(user_id, body.role)
    partner = {"user_id": user_id, "email": body.email, "name": body.name, "role": body.role, "organization_name": body.organization_name, "partner_status": "active", "wysh_id": wysh_id, "password_hash": hash_password(body.password), "auth_provider": "password", "created_at": datetime.now(timezone.utc).isoformat()}
    await users.insert_one(partner)
    partner.pop("_id", None); partner.pop("password_hash", None)
    await write_audit(user["user_id"], "partner.provision", "user", user_id, {"role": body.role})
    return partner


@router.post("/google/exchange")
async def google_exchange(body: GoogleExchangeBody, response: Response):
    """Exchange Emergent Google session_id for our session_token."""
    try:
        r = requests.get(
            settings.EMERGENT_AUTH_URL,
            headers={"X-Session-ID": body.session_id},
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google auth failed: {e}")
    data = r.json()
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="No email from Google")

    user = await users.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = f"usr_{uuid.uuid4().hex[:16]}"
        wysh_id = await _create_wysh_id(user_id, "patient")
        doc = {
            "user_id": user_id,
            "email": email,
            "name": data.get("name") or email.split("@")[0],
            "role": "patient",
            "phone": None,
            "specialty": None,
            "wysh_id": wysh_id,
            "password_hash": None,
            "auth_provider": "google",
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await users.insert_one(doc)
        doc.pop("_id", None)
        user = doc
        await write_audit(user_id, "user.signup", "user", user_id, {"provider": "google"})

    session_token = data["session_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "session_token": session_token,
            "user_id": user["user_id"],
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    await write_audit(user["user_id"], "user.login", "user", user["user_id"], {"provider": "google"})

    response.set_cookie(
        key="session_token", value=session_token,
        max_age=7 * 24 * 3600, httponly=True, secure=True, samesite="none", path="/",
    )
    user.pop("password_hash", None)
    return {"token": session_token, "user": user}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    user.pop("password_hash", None)
    return user


@router.post("/logout")
async def logout(response: Response, authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        tok = authorization.split(" ", 1)[1].strip()
        await sessions.delete_one({"session_token": tok})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}
