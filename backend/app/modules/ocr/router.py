"""Secure document intake, medical extraction, and reviewed EMR commits."""
import uuid
import asyncio
import io
from datetime import datetime, timezone
from typing import Literal, Optional
import pymupdf
from PIL import Image
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from ...core.audit import write_audit
from ...core.config import settings
from ...core.db import appointments, files as files_col, lab_reports, prescriptions, records
from ...core.deps import get_current_user
from ...core.security import decode_jwt
from ..ai.llm import extract_medical_document
from ..storage.service import get_object, put_object

router = APIRouter(prefix="/ocr", tags=["ocr"])
DocumentKind = Literal["prescription", "lab_report"]
IMAGE_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_MIME = IMAGE_MIME | {"application/pdf"}


class ReviewBody(BaseModel):
    decision: Literal["approved", "rejected"]
    extracted: dict


def _collection(kind: DocumentKind):
    return prescriptions if kind == "prescription" else lab_reports


def _to_image_for_extraction(data: bytes, content_type: str) -> bytes:
    if content_type != "application/pdf":
        return data
    pdf = pymupdf.open(stream=data, filetype="pdf")
    if not pdf.page_count:
        raise ValueError("PDF has no pages")
    pages = []
    for index in range(pdf.page_count):
        pixmap = pdf.load_page(index).get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
        pages.append(Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB"))
    width = max(page.width for page in pages)
    height = sum(page.height for page in pages)
    combined = Image.new("RGB", (width, height), "white")
    offset = 0
    for page in pages:
        combined.paste(page, (0, offset)); offset += page.height
    output = io.BytesIO(); combined.save(output, format="PNG")
    return output.getvalue()


async def _can_access(document: dict, user: dict) -> bool:
    if document["patient_id"] == user["user_id"]:
        return True
    if user["role"] != "doctor":
        return False
    relationship = await appointments.find_one({"doctor_id": user["user_id"], "patient_id": document["patient_id"], "status": {"$in": ["scheduled", "completed"]}}, {"_id": 0, "appointment_id": 1})
    return bool(relationship)


async def _upload_document(kind: DocumentKind, file: UploadFile, user: dict) -> dict:
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Unsupported type. Use JPEG, PNG, WEBP, or PDF.")
    data = await file.read()
    if not data or len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be between 1 byte and 20MB")
    extension = (file.filename or "document").rsplit(".", 1)[-1].lower()
    file_id = f"file_{uuid.uuid4().hex[:16]}"
    storage_path = f"{settings.APP_NAME}/uploads/{user['user_id']}/{file_id}.{extension}"
    try:
        stored = await asyncio.to_thread(put_object, storage_path, data, file.content_type)
    except Exception:
        raise HTTPException(status_code=502, detail="Secure storage is temporarily unavailable")
    file_doc = {
        "file_id": file_id, "owner_id": user["user_id"], "storage_path": stored["path"],
        "original_filename": file.filename or "document", "content_type": file.content_type,
        "size": stored.get("size", len(data)), "kind": kind, "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await files_col.insert_one(file_doc)
    try:
        image_bytes = await asyncio.to_thread(_to_image_for_extraction, data, file.content_type)
        extracted = await extract_medical_document(image_bytes, kind)
        extraction_status = "complete" if extracted else "failed"
    except Exception:
        extracted = {"overall_confidence": 0.0}
        extraction_status = "failed"
    document_id = f"{'pres' if kind == 'prescription' else 'lab'}_{uuid.uuid4().hex[:16]}"
    document = {
        "document_id": document_id, "patient_id": user["user_id"], "uploaded_by": user["user_id"],
        "file_id": file_id, "storage_path": stored["path"], "document_kind": kind,
        "extracted": extracted, "extraction_status": extraction_status, "review_state": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if kind == "prescription":
        document["prescription_id"] = document_id
        document["status"] = "needs_review"
    else:
        document["lab_report_id"] = document_id
    await _collection(kind).insert_one(document)
    document.pop("_id", None)
    await write_audit(user["user_id"], "document.extract", kind, document_id, {"file_id": file_id, "status": extraction_status})
    return document


@router.post("/documents/{kind}")
async def upload_document(kind: DocumentKind, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    return await _upload_document(kind, file, user)


@router.post("/prescriptions")
async def upload_prescription(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    return await _upload_document("prescription", file, user)


@router.get("/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    prescription_docs = await prescriptions.find({"patient_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    lab_docs = await lab_reports.find({"patient_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return sorted(prescription_docs + lab_docs, key=lambda item: item["created_at"], reverse=True)


@router.get("/prescriptions")
async def list_prescriptions(user: dict = Depends(get_current_user)):
    return await prescriptions.find({"patient_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)


async def _get_document(document_id: str) -> tuple[dict, DocumentKind]:
    document = await prescriptions.find_one({"document_id": document_id}, {"_id": 0})
    if document:
        return document, "prescription"
    document = await lab_reports.find_one({"document_id": document_id}, {"_id": 0})
    if document:
        return document, "lab_report"
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/documents/{document_id}")
async def get_document(document_id: str, user: dict = Depends(get_current_user)):
    document, _ = await _get_document(document_id)
    if not await _can_access(document, user):
        raise HTTPException(status_code=403, detail="Not allowed")
    return document


@router.post("/documents/{document_id}/review")
async def review_document(document_id: str, body: ReviewBody, user: dict = Depends(get_current_user)):
    document, kind = await _get_document(document_id)
    if not await _can_access(document, user):
        raise HTTPException(status_code=403, detail="Not allowed")
    if document.get("review_state") != "pending":
        return document
    now = datetime.now(timezone.utc).isoformat()
    updates = {"review_state": body.decision, "reviewed_by": user["user_id"], "reviewed_at": now, "reviewed_extraction": body.extracted}
    record = None
    if body.decision == "approved":
        record = {
            "record_id": f"rec_{uuid.uuid4().hex[:16]}", "patient_id": document["patient_id"], "author_id": user["user_id"],
            "record_type": kind, "title": "Reviewed prescription" if kind == "prescription" else "Reviewed lab report",
            "summary": "AI extraction reviewed and committed", "file_id": document["file_id"], "data": body.extracted,
            "source_document_id": document_id, "created_at": now,
        }
        updates["emr_record_id"] = record["record_id"]
    result = await _collection(kind).update_one({"document_id": document_id, "review_state": "pending"}, {"$set": {"review_state": "committing", "reviewed_by": user["user_id"], "reviewed_at": now, "reviewed_extraction": body.extracted}})
    if not result.modified_count:
        latest, _ = await _get_document(document_id)
        return latest
    if record:
        try:
            await records.insert_one(record)
            record.pop("_id", None)
        except Exception:
            await _collection(kind).update_one({"document_id": document_id, "review_state": "committing"}, {"$set": {"review_state": "pending"}, "$unset": {"reviewed_by": "", "reviewed_at": "", "reviewed_extraction": ""}})
            raise HTTPException(status_code=503, detail="Record commit could not be completed")
    await _collection(kind).update_one({"document_id": document_id, "review_state": "committing"}, {"$set": updates})
    reviewed, _ = await _get_document(document_id)
    await write_audit(user["user_id"], "document.review", kind, document_id, {"decision": body.decision})
    return reviewed


@router.get("/files/{file_id}")
async def download_file(file_id: str, user: dict = Depends(get_current_user)):
    file_doc = await files_col.find_one({"file_id": file_id, "is_deleted": False}, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    if file_doc["owner_id"] != user["user_id"]:
        document = await prescriptions.find_one({"file_id": file_id}, {"_id": 0}) or await lab_reports.find_one({"file_id": file_id}, {"_id": 0})
        if not document or not await _can_access(document, user):
            raise HTTPException(status_code=403, detail="Not allowed")
    try:
        content, content_type = await asyncio.to_thread(get_object, file_doc["storage_path"])
    except Exception:
        raise HTTPException(status_code=502, detail="Secure storage is temporarily unavailable")
    return Response(content=content, media_type=file_doc.get("content_type") or content_type)