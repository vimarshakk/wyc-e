"""Invoice foundation. Payment checkout activates only after Razorpay is configured."""
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, conint
from ...core.audit import write_audit
from ...core.db import appointments, invoice_lines, invoices, users
from ...core.deps import get_current_user, require_role

router = APIRouter(prefix="/billing", tags=["billing"])


class InvoiceLine(BaseModel):
    description: str = Field(min_length=1, max_length=160)
    amount_paise: conint(gt=0, le=10_000_000)


class InvoiceCreate(BaseModel):
    patient_id: str
    due_at: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    lines: List[InvoiceLine] = Field(min_length=1, max_length=25)


async def _invoice_with_lines(invoice: dict) -> dict:
    lines = await invoice_lines.find({"invoice_id": invoice["invoice_id"]}, {"_id": 0}).sort("line_number", 1).to_list(50)
    return {**invoice, "lines": lines}


@router.post("/invoices")
async def create_invoice(body: InvoiceCreate, user: dict = Depends(require_role("doctor", "admin"))):
    patient = await users.find_one({"user_id": body.patient_id, "role": "patient"}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if user["role"] == "doctor":
        relationship = await appointments.find_one({"doctor_id": user["user_id"], "patient_id": body.patient_id}, {"_id": 0, "appointment_id": 1})
        if not relationship:
            raise HTTPException(status_code=403, detail="Patient is not in your care")
    now = datetime.now(timezone.utc).isoformat()
    invoice_id = f"inv_{uuid.uuid4().hex[:16]}"
    total = sum(line.amount_paise for line in body.lines)
    invoice = {"invoice_id": invoice_id, "patient_id": body.patient_id, "issued_by": user["user_id"], "currency": "INR", "total_paise": total, "status": "issued", "due_at": body.due_at, "notes": body.notes, "created_at": now}
    await invoices.insert_one(invoice)
    await invoice_lines.insert_many([{"line_id": f"line_{uuid.uuid4().hex[:16]}", "invoice_id": invoice_id, "line_number": index, "description": line.description, "amount_paise": line.amount_paise, "created_at": now} for index, line in enumerate(body.lines, start=1)])
    invoice.pop("_id", None)
    await write_audit(user["user_id"], "invoice.create", "invoice", invoice_id, {"patient_id": body.patient_id, "total_paise": total})
    return await _invoice_with_lines(invoice)


@router.get("/invoices/mine")
async def list_my_invoices(user: dict = Depends(get_current_user)):
    query = {"issued_by": user["user_id"]} if user["role"] in ("doctor", "admin") else {"patient_id": user["user_id"]}
    invoice_docs = await invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [await _invoice_with_lines(invoice) for invoice in invoice_docs]


@router.get("/patients")
async def billable_patients(user: dict = Depends(require_role("doctor", "admin"))):
    query = {} if user["role"] == "admin" else {"doctor_id": user["user_id"]}
    appointment_docs = await appointments.find(query, {"_id": 0, "patient_id": 1}).to_list(500)
    patient_ids = list({item["patient_id"] for item in appointment_docs})
    return await users.find({"user_id": {"$in": patient_ids}, "role": "patient"}, {"_id": 0, "password_hash": 0}).to_list(500) if patient_ids else []


@router.post("/invoices/{invoice_id}/checkout")
async def start_checkout(invoice_id: str, user: dict = Depends(get_current_user)):
    invoice = await invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not invoice or (invoice["patient_id"] != user["user_id"] and user["role"] != "admin"):
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not (os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET")):
        raise HTTPException(status_code=503, detail="Payments are not configured yet")
    raise HTTPException(status_code=501, detail="Payment checkout will activate after gateway verification")