from fastapi import APIRouter, Depends

from app.core.deps import current_user

router = APIRouter(prefix="/uhi", tags=["uhi"])


@router.get("/status")
async def status(user=Depends(current_user)):
    return {"user_id": user["sub"], "state": "NOT_ONBOARDED", "catalogue": [], "outbound_enabled": False}
