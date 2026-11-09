from fastapi import APIRouter, Depends

from app.core.deps import current_user

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/summary")
async def summary(user=Depends(current_user)):
    return {"patient_id": user["sub"], "currency": "INR", "outstanding": 0, "invoices": []}
