"""Clinic organizer OAuth for Google Calendar and Meet."""
import os
import secrets
import uuid
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from ...core.audit import write_audit
from ...core.db import calendar_connections, calendar_oauth_states
from ...core.deps import require_role
from .service import CALENDAR_SCOPE, encrypt_tokens

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _client_config() -> dict:
    return {"web": {"client_id": os.environ["GOOGLE_CLIENT_ID"], "client_secret": os.environ["GOOGLE_CLIENT_SECRET"], "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}


@router.get("/status")
async def connection_status(user: dict = Depends(require_role("admin"))):
    connection = await calendar_connections.find_one({"active": True}, {"_id": 0, "organizer_email": 1, "updated_at": 1})
    return {"connected": bool(connection), "organizer_email": connection.get("organizer_email") if connection else None}


@router.get("/connect")
async def connect_calendar(request: Request, user: dict = Depends(require_role("admin"))):
    redirect_uri = os.environ.get("GOOGLE_CALENDAR_REDIRECT_URI")
    if not redirect_uri or not redirect_uri.startswith("https://"):
        raise HTTPException(status_code=503, detail="Secure Google Calendar callback is not configured")
    flow = Flow.from_client_config(_client_config(), scopes=[CALENDAR_SCOPE], redirect_uri=redirect_uri)
    authorization_url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    await calendar_oauth_states.insert_one({"state": state, "organizer_id": user["user_id"], "redirect_uri": redirect_uri, "status": "pending", "created_at": datetime.now(timezone.utc).isoformat()})
    return {"authorization_url": authorization_url}


@router.get("/callback", name="calendar_callback")
async def calendar_callback(request: Request, state: str, code: str | None = None, error: str | None = None):
    saved_state = await calendar_oauth_states.find_one({"state": state, "status": "pending"}, {"_id": 0})
    if not saved_state or error or not code:
        raise HTTPException(status_code=400, detail="Calendar authorization was not completed")
    await calendar_oauth_states.update_one({"state": state, "status": "pending"}, {"$set": {"status": "consumed", "consumed_at": datetime.now(timezone.utc).isoformat()}})
    async with httpx.AsyncClient(timeout=30) as client:
        token_response = await client.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": os.environ["GOOGLE_CLIENT_ID"], "client_secret": os.environ["GOOGLE_CLIENT_SECRET"], "redirect_uri": saved_state["redirect_uri"], "grant_type": "authorization_code"})
        token_response.raise_for_status()
        tokens = token_response.json()
        tokens.update({"token_uri": "https://oauth2.googleapis.com/token", "client_id": os.environ["GOOGLE_CLIENT_ID"], "client_secret": os.environ["GOOGLE_CLIENT_SECRET"]})
        userinfo_response = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        userinfo_response.raise_for_status()
    await calendar_connections.update_many({"active": True}, {"$set": {"active": False}})
    connection = {"connection_id": f"gcal_{uuid.uuid4().hex[:16]}", "organizer_id": saved_state["organizer_id"], "organizer_email": userinfo_response.json().get("email"), "encrypted_tokens": encrypt_tokens(tokens), "active": True, "updated_at": datetime.now(timezone.utc).isoformat()}
    await calendar_connections.insert_one(connection)
    await write_audit(saved_state["organizer_id"], "calendar.organizer.connect", "calendar_connection", connection["connection_id"])
    app_origin = saved_state["redirect_uri"].split("/api/calendar/callback", 1)[0]
    return RedirectResponse(f"{app_origin}/app/admin?calendar=connected")