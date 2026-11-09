from fastapi import APIRouter, Depends

from app.core.deps import current_user

router = APIRouter(prefix="/records", tags=["records"])


@router.get("")
async def records(user=Depends(current_user)):
    return {"patient_id": user["sub"], "items": []}
