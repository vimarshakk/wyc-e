from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import current_user

router = APIRouter(prefix="/nhcx", tags=["nhcx"])


class CallbackReceipt(BaseModel):
    timestamp: str
    api_call_id: str
    correlation_id: str
    result: dict
    error: dict = {}


@router.get("/status")
async def status_endpoint(user=Depends(current_user)):
    return {"user_id": user["sub"], "state": "DRAFT", "outbound_enabled": False, "onboarding_required": True}


@router.post("/callback", status_code=status.HTTP_202_ACCEPTED)
async def callback(receipt: CallbackReceipt, x_nhcx_secret: str | None = Header(default=None)):
    if settings.nhcx_callback_secret and x_nhcx_secret != settings.nhcx_callback_secret:
        raise HTTPException(401, "Unverified callback")
    return {"timestamp": receipt.timestamp or datetime.now(timezone.utc).isoformat(), "api_call_id": receipt.api_call_id, "correlation_id": receipt.correlation_id, "result": {**receipt.result, "protocol_status": "request.queued"}, "error": {"code": "", "message": ""}}
