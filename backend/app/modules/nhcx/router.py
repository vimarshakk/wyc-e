import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.db import nhcx_episodes
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