from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.core.deps import current_user

router = APIRouter(prefix="/abdm", tags=["abdm"])


@router.get("/status")
async def status(user=Depends(current_user)):
    return {"user_id": user["sub"], "m1": "FOUNDATION", "m2": "FOUNDATION", "m3": "FOUNDATION", "m4": "NOT_CONFIGURED", "m5": "NOT_CONFIGURED", "external_calls_enabled": False}


@router.post("/callbacks/{stage}")
async def callback(stage: str, x_callback_secret: str | None = Header(default=None)):
    if settings.abdm_callback_secret and x_callback_secret != settings.abdm_callback_secret:
        raise HTTPException(401, "Invalid callback secret")
    return {"accepted": True, "stage": stage.upper(), "status": "QUEUED"}
