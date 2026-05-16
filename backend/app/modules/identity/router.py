"""WyshID identity endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from ...core.db import wysh_ids
from ...core.deps import get_current_user

router = APIRouter(prefix="/wyshid", tags=["wyshid"])


@router.get("/me")
async def my_wysh_id(user: dict = Depends(get_current_user)):
    rec = await wysh_ids.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="WyshID not found")
    return {
        **rec,
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "picture": user.get("picture"),
    }


@router.get("/{wysh_id}")
async def lookup(wysh_id: str, user: dict = Depends(get_current_user)):
    """Doctors/admins can look up patients by WyshID."""
    if user["role"] not in ("doctor", "admin"):
        raise HTTPException(status_code=403, detail="Not allowed")
    rec = await wysh_ids.find_one({"wysh_id": wysh_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    from ...core.db import users
    u = await users.find_one({"user_id": rec["user_id"]}, {"_id": 0, "password_hash": 0})
    return {**rec, "user": u}
