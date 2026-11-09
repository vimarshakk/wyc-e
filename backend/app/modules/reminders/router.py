from fastapi import APIRouter, Depends

from app.core.deps import current_user

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("")
async def reminders(user=Depends(current_user)):
    return {"patient_id": user["sub"], "items": []}
