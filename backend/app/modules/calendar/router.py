from fastapi import APIRouter, Depends

from app.core.deps import current_user

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/status")
async def status(user=Depends(current_user)):
    return {"connected": False, "provider": "google", "user_id": user["sub"]}


@router.get("/oauth/callback")
async def oauth_callback(code: str | None = None):
    return {"connected": bool(code), "message": "OAuth callback received; token exchange remains configuration-gated."}
