"""Google Calendar and Meet event creation for teleconsultations."""
import asyncio
import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from ...core.config import settings
from ...core.db import calendar_connections

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def _cipher() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.TOKEN_ENCRYPTION_KEY.encode()).digest())
    return Fernet(key)


def encrypt_tokens(tokens: dict) -> str:
    return _cipher().encrypt(json.dumps(tokens).encode()).decode()


def decrypt_tokens(value: str) -> dict:
    return json.loads(_cipher().decrypt(value.encode()).decode())


async def calendar_connected() -> bool:
    return bool(await calendar_connections.find_one({"active": True}, {"_id": 0, "connection_id": 1}))


async def _calendar_service():
    connection = await calendar_connections.find_one({"active": True}, {"_id": 0})
    if not connection:
        return None
    tokens = decrypt_tokens(connection["encrypted_tokens"])
    credentials = Credentials.from_authorized_user_info(tokens, [CALENDAR_SCOPE])
    if credentials.expired and credentials.refresh_token:
        await asyncio.to_thread(credentials.refresh, GoogleRequest())
        tokens.update({"token": credentials.token, "expiry": credentials.expiry.isoformat() if credentials.expiry else None})
        await calendar_connections.update_one({"connection_id": connection["connection_id"]}, {"$set": {"encrypted_tokens": encrypt_tokens(tokens), "updated_at": datetime.now(timezone.utc).isoformat()}})
    return await asyncio.to_thread(build, "calendar", "v3", credentials=credentials, cache_discovery=False)


async def create_or_update_meet_event(appointment: dict) -> dict:
    service = await _calendar_service()
    if not service:
        return {"video_link_status": "organizer_not_connected"}
    start = datetime.fromisoformat(appointment["scheduled_at"].replace("Z", "+00:00"))
    end = start + timedelta(minutes=30)
    event_body = {
        "summary": "WyshCare Consultation",
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Kolkata"},
        "conferenceData": {"createRequest": {"requestId": f"meet-{appointment['appointment_id']}"}},
    }
    if appointment.get("google_event_id"):
        result = await asyncio.to_thread(lambda: service.events().update(calendarId="primary", eventId=appointment["google_event_id"], body=event_body, conferenceDataVersion=1).execute())
    else:
        result = await asyncio.to_thread(lambda: service.events().insert(calendarId="primary", body=event_body, conferenceDataVersion=1).execute())
    entry_points = result.get("conferenceData", {}).get("entryPoints", [])
    meeting_url = next((item.get("uri") for item in entry_points if item.get("entryPointType") == "video"), None)
    return {"google_event_id": result["id"], "video_link_status": "ready" if meeting_url else "preparing", "meeting_url": meeting_url}