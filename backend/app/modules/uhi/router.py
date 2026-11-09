"""UHI EUA transaction foundation. No network traffic occurs before onboarding."""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.db import uhi_transactions
from ...core.deps import require_role

router = APIRouter(prefix="/uhi", tags=["uhi"])

class SearchBody(BaseModel):
    city: str = Field(pattern=r"^std:[0-9]{3}$")
    radius_km: float = Field(gt=0, le=100)

@router.get("/status")
async def status(user: dict = Depends(require_role("patient"))):
    configured = all(os.environ.get(key) for key in ("UHI_SUBSCRIBER_ID", "UHI_KEY_ID", "UHI_CONSUMER_URI", "UHI_DOMAIN"))
    return {"configured": configured, "network": "inactive" if not configured else "onboarding_required"}

@router.post("/search", status_code=202)
async def search(body: SearchBody, user: dict = Depends(require_role("patient"))):
    if not all(os.environ.get(key) for key in ("UHI_SUBSCRIBER_ID", "UHI_KEY_ID", "UHI_CONSUMER_URI", "UHI_DOMAIN")):
        raise HTTPException(status_code=503, detail="UHI is not configured")
    transaction = {"transaction_id": f"uhi_{uuid.uuid4().hex[:16]}", "patient_id": user["user_id"], "action": "search", "status": "created", "created_at": datetime.now(timezone.utc).isoformat()}
    await uhi_transactions.insert_one(transaction)
    transaction.pop("_id", None)
    raise HTTPException(status_code=501, detail="UHI signing and verified network adapter are pending onboarding")

@router.get("/transactions/mine")
async def my_transactions(user: dict = Depends(require_role("patient"))):
    return await uhi_transactions.find({"patient_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)