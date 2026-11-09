from fastapi import APIRouter, Depends

from app.core.deps import current_user

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/wyshid")
async def wyshid(user=Depends(current_user)):
    return {"wysh_id": f"WYC-{user['sub'][:8].upper()}", "verified": False, "user_id": user["sub"]}
