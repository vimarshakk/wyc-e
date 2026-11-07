"""ABDM HIE-CM M2 transaction and callback foundation; all PHI stays server-side."""
import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone
from datetime import timedelta
import httpx
from cryptography.fernet import Fernet
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives import hashes
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from ...core.audit import write_audit
from ...core.config import settings
from ...core.db import abdm_callback_events, abdm_consents, abdm_patient_links, abdm_transactions
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


class AbhaOtpStart(BaseModel):
    aadhaar_number: str = Field(pattern="^[0-9]{12}$")
    consent_agreed: bool


class AbhaOtpVerify(BaseModel):
    operation_id: str
    otp: str = Field(pattern="^[0-9]{4,8}$")
    communication_mobile: str = Field(pattern="^[0-9]{10}$")


class ConsentRequestBody(BaseModel):
    hi_types: list[str] = Field(min_length=1, max_length=8)
    from_at: datetime
    to_at: datetime
    erase_at: datetime
    purpose_code: str = Field(default="CAREMGT", pattern="^(CAREMGT|BTG|PUBHLTH|HPAYMT|DSRCH|PATRQT)$")


def _cipher() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.JWT_SECRET.encode()).digest()))


def _enc(value: str) -> str:
    return _cipher().encrypt(value.encode()).decode()


def _dec(value: str) -> str:
    return _cipher().decrypt(value.encode()).decode()


def _abha_url(path: str) -> str:
    return f"{os.environ['ABDM_ABHA_URL'].rstrip('/')}/{path.lstrip('/')}"


def _gateway_url(path: str) -> str:
    base = os.environ["ABDM_GATEWAY_URL"].rstrip("/")
    suffix = "/api/hiecm/gateway/v3"
    return f"{base if base.endswith(suffix) else base + suffix}/{path.lstrip('/')}"


async def _abha_public_key() -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(_abha_url("profile/public/certificate"))
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="ABHA public certificate is unavailable")
    try:
        return response.json().get("publicKey") or response.json().get("certificate") or response.text
    except ValueError:
        return response.text


def _rsa_encrypt(value: str, certificate: str) -> str:
    if "BEGIN CERTIFICATE" in certificate:
        public_key = x509.load_pem_x509_certificate(certificate.encode()).public_key()
    else:
        public_key = load_der_public_key(base64.b64decode(certificate))
    encrypted = public_key.encrypt(value.encode(), padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
    return base64.b64encode(encrypted).decode()


def _headers(token: str, request_id: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-CM-ID": os.environ["ABDM_CM_ID"], "X-HIP-ID": os.environ["ABDM_FACILITY_ID"], "REQUEST-ID": request_id, "TIMESTAMP": datetime.now(timezone.utc).isoformat(), "Content-Type": "application/json"}


async def _session() -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(_gateway_url("sessions"), headers={"X-CM-ID": os.environ["ABDM_CM_ID"], "REQUEST-ID": str(uuid.uuid4()), "TIMESTAMP": datetime.now(timezone.utc).isoformat()}, json={"clientId": os.environ["ABDM_CLIENT_ID"], "clientSecret": os.environ["ABDM_CLIENT_SECRET"]})
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


@router.get("/my-status")
async def my_abdm_status(user: dict = Depends(require_role("patient"))):
    link = await abdm_patient_links.find_one({"patient_id": user["user_id"]}, {"_id": 0, "status": 1, "updated_at": 1})
    consents = await abdm_consents.find({"patient_id": user["user_id"]}, {"_id": 0, "consent_id": 1, "status": 1, "created_at": 1}).sort("created_at", -1).to_list(50)
    return {"link_status": link.get("status", "not_linked") if link else "not_linked", "consents": consents, "record_discovery": "pending_sandbox_flow", "locker": "pending_sandbox_flow"}


@router.post("/abha/otp/start", status_code=202)
async def start_abha_otp(body: AbhaOtpStart, user: dict = Depends(require_role("patient"))):
    if not body.consent_agreed:
        raise HTTPException(status_code=400, detail="Aadhaar enrollment consent is required")
    request_id = str(uuid.uuid4())
    headers = _headers(await _session(), request_id)
    certificate = await _abha_public_key()
    async with httpx.AsyncClient(timeout=30) as client:
        otp_request = await client.post(_abha_url("enrollment/request-otp/aadhaar-otp"), headers=headers, json={"scope": ["abha-enrol"], "loginHint": "aadhaar", "loginId": _rsa_encrypt(body.aadhaar_number, certificate), "otpSystem": "aadhaar", "txnId": ""})
    if otp_request.status_code >= 400 or not otp_request.json().get("txnId"):
        raise HTTPException(status_code=502, detail="ABHA OTP could not be requested")
    operation_id = f"abha_{uuid.uuid4().hex[:16]}"
    await abdm_transactions.insert_one({"transaction_id": operation_id, "patient_id": user["user_id"], "kind": "abha_aadhaar_enrol", "status": "otp_sent", "encrypted_txn": _enc(otp_request.json()["txnId"]), "consent_code": "abha-enrollment", "consent_version": "1.4", "consent_accepted_at": datetime.now(timezone.utc).isoformat(), "created_at": datetime.now(timezone.utc).isoformat()})
    await write_audit(user["user_id"], "abdm.abha.otp.start", "abdm_transaction", operation_id)
    return {"operation_id": operation_id, "status": "otp_sent"}


@router.post("/abha/otp/verify")
async def verify_abha_otp(body: AbhaOtpVerify, user: dict = Depends(require_role("patient"))):
    operation = await abdm_transactions.find_one({"transaction_id": body.operation_id, "patient_id": user["user_id"], "kind": "abha_aadhaar_enrol", "status": "otp_sent"}, {"_id": 0})
    if not operation:
        raise HTTPException(status_code=409, detail="ABHA OTP operation is unavailable")
    certificate = await _abha_public_key()
    headers = {"REQUEST-ID": str(uuid.uuid4()), "TIMESTAMP": datetime.now(timezone.utc).isoformat()}
    payload = {"authData": {"authMethods": ["otp"], "otp": {"txnId": _dec(operation["encrypted_txn"]), "otpValue": _rsa_encrypt(body.otp, certificate), "mobile": _rsa_encrypt(body.communication_mobile, certificate)}}, "consent": {"code": "abha-enrollment", "version": "1.4"}}
    async with httpx.AsyncClient(timeout=30) as client:
        verified = await client.post(_abha_url("enrollment/enrol/byaadhaar-otp"), headers=headers, json=payload)
    if verified.status_code >= 400:
        raise HTTPException(status_code=400, detail="ABHA OTP verification failed")
    await abdm_transactions.update_one({"transaction_id": body.operation_id}, {"$set": {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat()}, "$unset": {"encrypted_txn": ""}})
    await abdm_patient_links.update_one({"patient_id": user["user_id"]}, {"$set": {"patient_id": user["user_id"], "status": "abha_verified", "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    await write_audit(user["user_id"], "abdm.abha.otp.verify", "abdm_transaction", body.operation_id)
    return {"verified": True, "status": "abha_verified"}


@router.post("/consents/request", status_code=202)
async def request_consent(body: ConsentRequestBody, user: dict = Depends(require_role("patient"))):
    if body.to_at <= body.from_at or body.erase_at <= body.to_at:
        raise HTTPException(status_code=400, detail="Consent dates are invalid")
    abha_link = await abdm_patient_links.find_one({"patient_id": user["user_id"], "status": "abha_verified"}, {"_id": 0, "patient_id": 1})
    if not abha_link:
        raise HTTPException(status_code=409, detail="Verify ABHA before requesting record-sharing consent")
    request_id = str(uuid.uuid4())
    consent_id = f"cons_{uuid.uuid4().hex[:16]}"
    token = await _session()
    payload = {"consent": {"purpose": {"text": "Care Management", "code": body.purpose_code, "refUri": "https://wyshcare.in/consent"}, "hiTypes": body.hi_types, "permission": {"accessMode": "VIEW", "dateRange": {"from": body.from_at.astimezone(timezone.utc).isoformat(), "to": body.to_at.astimezone(timezone.utc).isoformat()}, "dataEraseAt": body.erase_at.astimezone(timezone.utc).isoformat()}}}
    await abdm_consents.insert_one({"consent_id": consent_id, "request_id": request_id, "patient_id": user["user_id"], "status": "submitted", "hi_types": body.hi_types, "created_at": datetime.now(timezone.utc).isoformat()})
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{os.environ['ABDM_GATEWAY_URL'].rstrip('/')}/api/hiecm/consent/v3/request/init", headers=_headers(token, request_id), json=payload)
    if response.status_code >= 400:
        await abdm_consents.update_one({"consent_id": consent_id}, {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc).isoformat()}})
        raise HTTPException(status_code=502, detail="ABDM consent request was rejected")
    await write_audit(user["user_id"], "abdm.consent.request", "abdm_consent", consent_id, {"hi_types": body.hi_types})
    return {"consent_id": consent_id, "status": "submitted"}


@router.post("/v3/hiu/consent/request/on-init", status_code=202)
async def on_consent_init(request: Request, x_callback_secret: str | None = Header(default=None)):
    expected_secret = os.environ.get("ABDM_CALLBACK_SHARED_SECRET")
    if not x_callback_secret or not expected_secret or x_callback_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized callback")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Callback body must be an object")
    request_id = body.get("requestId")
    consent_request_id = body.get("consentRequestId")
    if not request_id or not consent_request_id:
        raise HTTPException(status_code=400, detail="Consent callback is incomplete")
    result = await abdm_callback_events.update_one({"event_type": "consent_init", "correlation_id": request_id}, {"$setOnInsert": {"event_type": "consent_init", "correlation_id": request_id, "received_at": datetime.now(timezone.utc).isoformat(), "status": "received"}}, upsert=True)
    if result.upserted_id:
        await abdm_consents.update_one({"request_id": request_id}, {"$set": {"abdm_consent_request_id": consent_request_id, "status": "awaiting_patient_decision", "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"status": "accepted"}


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