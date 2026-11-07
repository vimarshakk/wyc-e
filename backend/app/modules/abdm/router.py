"""ABDM HIE-CM M2 transaction and callback foundation; all PHI stays server-side."""
import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone
import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from ...core.audit import write_audit
from ...core.config import settings
from ...core.db import abdm_callback_events, abdm_patient_links, abdm_transactions
from ...core.deps import require_role

router = APIRouter(prefix="/abdm", tags=["abdm"])


class LinkTokenBody(BaseModel):
    patient_id: str
    patient_name: str = Field(min_length=2, max_length=120)
    abha_address: str = Field(min_length=3, max_length=120)
    abha_number: str | None = Field(default=None, max_length=32)
    gender: str = Field(pattern="^[MFODTU]$")
    year_of_birth: int = Field(ge=1900, le=2100)


class CareContextBody(BaseModel):
    patient_id: str
    reference: str = Field(min_length=1, max_length=120)
    display: str = Field(min_length=1, max_length=160)


def _cipher() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.JWT_SECRET.encode()).digest()))


def _enc(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def _dec(value: str) -> str:
    return _cipher().decrypt(value.encode()).decode()


def _headers(token: str, request_id: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-CM-ID": os.environ["ABDM_CM_ID"], "X-HIP-ID": os.environ["ABDM_FACILITY_ID"], "REQUEST-ID": request_id, "TIMESTAMP": datetime.now(timezone.utc).isoformat(), "Content-Type": "application/json"}


async def _session() -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{os.environ['ABDM_GATEWAY_URL'].rstrip('/')}/api/hiecm/gateway/v3/sessions", headers={"X-CM-ID": os.environ["ABDM_CM_ID"], "REQUEST-ID": str(uuid.uuid4()), "TIMESTAMP": datetime.now(timezone.utc).isoformat()}, json={"clientId": os.environ["ABDM_CLIENT_ID"], "clientSecret": os.environ["ABDM_CLIENT_SECRET"]})
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="ABDM sandbox session could not be created")
    token = response.json().get("accessToken")
    if not token:
        raise HTTPException(status_code=502, detail="ABDM sandbox session response was incomplete")
    return token


@router.get("/status")
async def abdm_status(user: dict = Depends(require_role("admin"))):
    required = ("ABDM_GATEWAY_URL", "ABDM_ABHA_URL", "ABDM_CM_ID", "ABDM_CLIENT_ID", "ABDM_CLIENT_SECRET", "ABDM_BRIDGE_BASE_URL", "ABDM_CALLBACK_SHARED_SECRET", "ABDM_FACILITY_ID")
    return {"sandbox_configured": all(os.environ.get(name) for name in required), "hie_cm": "M2 link-token ready", "m5": "internal production-readiness gate"}


@router.post("/hip/link-token", status_code=202)
async def generate_link_token(body: LinkTokenBody, user: dict = Depends(require_role("doctor", "admin"))):
    request_id = str(uuid.uuid4())
    await abdm_transactions.insert_one({"transaction_id": f"abdm_{uuid.uuid4().hex[:16]}", "request_id": request_id, "patient_id": body.patient_id, "kind": "hip_link_token", "status": "submitted", "created_at": datetime.now(timezone.utc).isoformat()})
    token = await _session()
    payload = {"abhaAddress": body.abha_address, "name": body.patient_name, "gender": body.gender, "yearOfBirth": str(body.year_of_birth)}
    if body.abha_number:
        payload["abhaNumber"] = body.abha_number
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{os.environ['ABDM_GATEWAY_URL'].rstrip('/')}/api/hiecm/v3/token/generate-token", headers=_headers(token, request_id), json=payload)
    if response.status_code >= 400:
        await abdm_transactions.update_one({"request_id": request_id}, {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc).isoformat()}})
        raise HTTPException(status_code=502, detail="ABDM link-token request was rejected")
    await write_audit(user["user_id"], "abdm.hip.link_token", "abdm_transaction", request_id, {"patient_id": body.patient_id})
    return {"request_id": request_id, "status": "submitted"}


@router.post("/hip/care-context", status_code=202)
async def link_care_context(body: CareContextBody, user: dict = Depends(require_role("doctor", "admin"))):
    patient_link = await abdm_patient_links.find_one({"patient_id": body.patient_id, "status": "token_ready"}, {"_id": 0})
    if not patient_link:
        raise HTTPException(status_code=409, detail="ABDM link token is not ready")
    request_id = str(uuid.uuid4())
    token = await _session()
    payload = {"patient": {"referenceNumber": body.reference, "display": body.display}, "careContexts": [{"referenceNumber": body.reference, "display": body.display}]}
    headers = _headers(token, request_id); headers["X-Link-Token"] = _dec(patient_link["encrypted_link_token"])
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{os.environ['ABDM_GATEWAY_URL'].rstrip('/')}/api/hiecm/hip/v3/link/carecontext", headers=headers, json=payload)
    await abdm_transactions.insert_one({"transaction_id": f"abdm_{uuid.uuid4().hex[:16]}", "request_id": request_id, "patient_id": body.patient_id, "kind": "hip_care_context", "status": "submitted" if response.status_code < 400 else "rejected", "created_at": datetime.now(timezone.utc).isoformat()})
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="ABDM care-context request was rejected")
    await write_audit(user["user_id"], "abdm.hip.care_context", "abdm_transaction", request_id, {"patient_id": body.patient_id})
    return {"request_id": request_id, "status": "submitted"}


@router.post("/v3/hip/token/on-generate-token", status_code=202)
async def on_generate_token(request: Request, x_callback_secret: str | None = Header(default=None)):
    if not x_callback_secret:
        raise HTTPException(status_code=401, detail="Unauthorized callback")
    expected_secret = os.environ.get("ABDM_CALLBACK_SHARED_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=503, detail="ABDM callback verification is not configured")
    if x_callback_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized callback")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Callback body must be an object")
    correlation_id = body.get("requestId") or body.get("request_id")
    if not correlation_id:
        raise HTTPException(status_code=400, detail="Callback correlation is required")
    transaction = await abdm_transactions.find_one({"request_id": correlation_id}, {"_id": 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Unknown transaction")
    result = await abdm_callback_events.update_one({"event_type": "link_token", "correlation_id": correlation_id}, {"$setOnInsert": {"event_type": "link_token", "correlation_id": correlation_id, "received_at": datetime.now(timezone.utc).isoformat(), "status": "received"}}, upsert=True)
    if result.upserted_id:
        link_token = body.get("linkToken") or body.get("link_token")
        if link_token:
            await abdm_patient_links.update_one({"patient_id": transaction["patient_id"]}, {"$set": {"patient_id": transaction["patient_id"], "encrypted_link_token": _enc(link_token), "status": "token_ready", "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
            await abdm_transactions.update_one({"request_id": correlation_id}, {"$set": {"status": "token_ready", "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"status": "accepted"}