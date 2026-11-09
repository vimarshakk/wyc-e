"""Auth dependency: accepts JWT (Bearer) OR Emergent Google session_token cookie."""
from datetime import datetime, timezone
from fastapi import Header, Cookie, HTTPException, Depends
from .security import decode_jwt
from .db import users, sessions

PROFESSIONAL_ROLES = {"doctor", "lab", "pharmacy", "insurer", "partner"}


async def _user_by_id(user_id: str) -> dict | None:
    return await users.find_one({"user_id": user_id}, {"_id": 0})


async def get_current_user(
    authorization: str | None = Header(default=None),
    session_token: str | None = Cookie(default=None),
) -> dict:
    # 1. JWT Bearer
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        payload = decode_jwt(token)
        if payload:
            user = await _user_by_id(payload["sub"])
            if user:
                return user
        # If Bearer decode fails, try as Google session token (frontend may send either)
        sess = await sessions.find_one({"session_token": token}, {"_id": 0})
        if sess:
            exp = sess.get("expires_at")
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp and exp >= datetime.now(timezone.utc):
                user = await _user_by_id(sess["user_id"])
                if user:
                    return user

    # 2. Cookie-based session_token (Emergent OAuth)
    if session_token:
        sess = await sessions.find_one({"session_token": session_token}, {"_id": 0})
        if sess:
            exp = sess.get("expires_at")
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp and exp >= datetime.now(timezone.utc):
                user = await _user_by_id(sess["user_id"])
                if user:
                    return user

    raise HTTPException(status_code=401, detail="Not authenticated")


def require_role(*roles: str):
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        if user.get("role") in PROFESSIONAL_ROLES and user.get("verification_status") != "APPROVED":
            raise HTTPException(status_code=403, detail="Account verification is pending")
        return user
    return _check
