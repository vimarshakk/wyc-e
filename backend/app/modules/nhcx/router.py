import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from ...core.db import nhcx_episodes, nhcx_events
from ...core.deps import require_role

router = APIRouter(prefix="/nhcx", tags=["nhcx"])

class EpisodeBody(BaseModel):
    patient_id: str
    policy_reference: str = Field(min_length=1, max_length=120)

@router.get("/status")
async def status(user: dict = Depends(require_role("doctor", "admin"))):
    configured = all(os.environ.get(key) for key in ("NHCX_PARTICIPANT_CODE", "NHCX_CALLBACK_SHARED_SECRET", "NHCX_PRIVATE_KEY_PEM"))
    return {"configured": configured, "network": "callback_onboarding_required", "states": ["DRAFT", "ELIGIBILITY_PENDING", "PREAUTH_PENDING", "CLAIM_PENDING"]}

@router.post("/episodes")
async def create_episode(body: EpisodeBody, user: dict = Depends(require_role("doctor", "admin"))):
    episode = {"episode_id": f"ep_{uuid.uuid4().hex[:16]}", "patient_id": body.patient_id, "policy_reference": body.policy_reference, "phase": "DRAFT", "created_by": user["user_id"], "created_at": datetime.now(timezone.utc).isoformat()}
    await nhcx_episodes.insert_one(episode); episode.pop("_id", None)
    return episode

@router.get("/episodes/mine")
async def my_episodes(user: dict = Depends(require_role("doctor", "admin"))):
    query = {} if user["role"] == "admin" else {"created_by": user["user_id"]}
    return await nhcx_episodes.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)

@router.post("/episodes/{episode_id}/eligibility", status_code=202)
async def eligibility(episode_id: str, user: dict = Depends(require_role("doctor", "admin"))):
    if not all(os.environ.get(key) for key in ("NHCX_PARTICIPANT_CODE", "NHCX_CALLBACK_SHARED_SECRET", "NHCX_PRIVATE_KEY_PEM", "NHCX_BASE_URL")):
        raise HTTPException(status_code=503, detail="NHCX callback onboarding is incomplete")
    result = await nhcx_episodes.update_one({"episode_id": episode_id, "phase": "DRAFT"}, {"$set": {"phase": "ELIGIBILITY_PENDING", "correlation_id": str(uuid.uuid4()), "updated_at": datetime.now(timezone.utc).isoformat()}})
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="Episode is not eligible for this transition")
    raise HTTPException(status_code=501, detail="Verified NHCX JWE adapter is pending callback onboarding")

@router.post("/v1/{entity}/on_{action}", status_code=202)
async def receive_callback(entity: str, action: str, request: Request, x_hcx_api_call_id: str | None = Header(default=None), x_hcx_correlation_id: str | None = Header(default=None), x_hcx_sender_code: str | None = Header(default=None), x_nhcx_callback_secret: str | None = Header(default=None)):
    if entity not in {"coverageeligibility", "preauth", "claim", "task", "payment", "insuranceplan"}:
        raise HTTPException(status_code=404, detail="Unsupported NHCX entity")
    expected_secret = os.environ.get("NHCX_CALLBACK_SHARED_SECRET")
    if not expected_secret or not x_nhcx_callback_secret or x_nhcx_callback_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized NHCX callback")
    body = await request.json()
    if not isinstance(body, dict) or not x_hcx_api_call_id or not x_hcx_correlation_id:
        raise HTTPException(status_code=400, detail="Invalid NHCX callback")
    await nhcx_events.update_one({"correlation_id": x_hcx_correlation_id, "api_call_id": x_hcx_api_call_id}, {"$setOnInsert": {"correlation_id": x_hcx_correlation_id, "api_call_id": x_hcx_api_call_id, "entity_type": entity, "action": action, "received_at": datetime.now(timezone.utc).isoformat(), "status": "queued"}}, upsert=True)
    participant_code = os.environ.get("NHCX_PARTICIPANT_CODE")
    if not participant_code:
        raise HTTPException(status_code=503, detail="NHCX participant configuration is incomplete")
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "api_call_id": x_hcx_api_call_id, "correlation_id": x_hcx_correlation_id, "result": {"sender_code": x_hcx_sender_code or "", "recipient_code": participant_code, "entity_type": entity, "protocol_status": "request.queued"}, "error": {"code": "", "message": ""}}