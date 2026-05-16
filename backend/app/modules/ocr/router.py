"""OCR + AI prescription intelligence pipeline."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Response, Query, Header
from typing import Optional
from ...core.db import prescriptions, files as files_col
from ...core.deps import get_current_user
from ...core.audit import write_audit
from ...core.config import settings
from ...core.security import decode_jwt
from ..storage.service import put_object, get_object
from ..ai.llm import extract_prescription

router = APIRouter(prefix="/ocr", tags=["ocr"])

ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


@router.post("/prescriptions")
async def upload_and_extract(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported type: {file.content_type}. Use JPEG/PNG/WEBP.")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    ext = (file.filename or "img.png").rsplit(".", 1)[-1].lower()
    file_id = f"file_{uuid.uuid4().hex[:16]}"
    path = f"{settings.APP_NAME}/prescriptions/{user['user_id']}/{file_id}.{ext}"

    try:
        result = put_object(path, data, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")

    await files_col.insert_one({
        "file_id": file_id,
        "owner_id": user["user_id"],
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "kind": "prescription_image",
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    try:
        extracted = await extract_prescription(data)
    except Exception as e:
        extracted = {"medications": [], "overall_confidence": 0.0, "_error": str(e)}

    pres_id = f"pres_{uuid.uuid4().hex[:16]}"
    doc = {
        "prescription_id": pres_id,
        "patient_id": user["user_id"],
        "uploaded_by": user["user_id"],
        "file_id": file_id,
        "storage_path": result["path"],
        "extracted": extracted,
        "status": "extracted" if extracted.get("medications") else "needs_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await prescriptions.insert_one(doc)
    await write_audit(user["user_id"], "ocr.prescription.extract", "prescription", pres_id,
                      {"file_id": file_id, "med_count": len(extracted.get("medications", []))})
    doc.pop("_id", None)
    return doc


@router.get("/prescriptions")
async def list_my_prescriptions(user: dict = Depends(get_current_user)):
    cur = prescriptions.find({"patient_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(200)
    return await cur.to_list(200)


@router.get("/prescriptions/{pres_id}")
async def get_prescription(pres_id: str, user: dict = Depends(get_current_user)):
    rec = await prescriptions.find_one({"prescription_id": pres_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if rec["patient_id"] != user["user_id"] and user["role"] not in ("doctor", "admin"):
        raise HTTPException(status_code=403, detail="Not allowed")
    return rec


@router.get("/files/{file_id}")
async def download_file(
    file_id: str,
    authorization: Optional[str] = Header(default=None),
    auth: Optional[str] = Query(default=None),
):
    """Download a file. Supports query-param auth for <img src=>."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif auth:
        token = auth
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_jwt(token)
    if not payload:
        # Could be Google session_token; check sessions
        from ...core.db import sessions
        sess = await sessions.find_one({"session_token": token}, {"_id": 0})
        if not sess:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = sess["user_id"]
    else:
        user_id = payload["sub"]

    rec = await files_col.find_one({"file_id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    # Owner OR doctor/admin (role check would need user fetch; keep owner-only for simplicity here)
    if rec["owner_id"] != user_id:
        from ...core.db import users
        u = await users.find_one({"user_id": user_id}, {"_id": 0})
        if not u or u.get("role") not in ("doctor", "admin"):
            raise HTTPException(status_code=403, detail="Not allowed")
    try:
        data, ctype = get_object(rec["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")
    return Response(content=data, media_type=rec.get("content_type") or ctype)
