from fastapi import APIRouter, Depends, File, UploadFile

from app.core.deps import current_user

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), user=Depends(current_user)):
    return {"filename": file.filename, "content_type": file.content_type, "patient_id": user["sub"], "status": "REVIEW_REQUIRED"}
