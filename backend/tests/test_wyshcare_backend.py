"""WyshCare backend integration tests.

Covers: health, auth (signup/login/me), WyshID, records, appointments,
OCR prescription upload, admin endpoints, and audit-log writes.
"""
import io
import os
import re
import uuid
import pytest
import requests
from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    # frontend .env value (testing only)
    BASE = "https://care-platform-v1.preview.emergentagent.com"
BASE = BASE.rstrip("/")
API = f"{BASE}/api"
PASSWORD = "TestPass123!"

# Unique suffix so reruns don't 409 on email
SUFFIX = uuid.uuid4().hex[:6]
PATIENT_EMAIL = f"patient_{SUFFIX}@wyshcare.io"
DOCTOR_EMAIL = f"doctor_{SUFFIX}@wyshcare.io"
ADMIN_EMAIL = f"admin_{SUFFIX}@wyshcare.io"

state = {}


# ---------- Health ----------
class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"


# ---------- Auth: signup / login / me ----------
class TestAuth:
    def test_signup_patient(self):
        r = requests.post(f"{API}/auth/signup", json={
            "email": PATIENT_EMAIL, "password": PASSWORD,
            "name": "Test Patient", "role": "patient",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body and isinstance(body["token"], str)
        u = body["user"]
        assert u["email"] == PATIENT_EMAIL
        assert u["role"] == "patient"
        assert re.match(r"^WYSH-[A-F0-9]{4}-[A-F0-9]{4}$", u["wysh_id"])
        assert u["user_id"].startswith("usr_")
        assert "password_hash" not in u
        state["patient_token"] = body["token"]
        state["patient_id"] = u["user_id"]
        state["patient_wysh"] = u["wysh_id"]

    def test_signup_doctor(self):
        r = requests.post(f"{API}/auth/signup", json={
            "email": DOCTOR_EMAIL, "password": PASSWORD,
            "name": "Dr Test", "role": "doctor", "specialty": "Cardiology",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        state["doctor_token"] = b["token"]
        state["doctor_id"] = b["user"]["user_id"]
        assert b["user"]["role"] == "doctor"
        assert b["user"]["specialty"] == "Cardiology"

    def test_signup_admin(self):
        r = requests.post(f"{API}/auth/signup", json={
            "email": ADMIN_EMAIL, "password": PASSWORD,
            "name": "Admin Test", "role": "admin",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        state["admin_token"] = b["token"]
        assert b["user"]["role"] == "admin"

    def test_signup_duplicate_returns_409(self):
        r = requests.post(f"{API}/auth/signup", json={
            "email": PATIENT_EMAIL, "password": PASSWORD,
            "name": "Dup", "role": "patient",
        })
        assert r.status_code == 409

    def test_login_success(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": PATIENT_EMAIL, "password": PASSWORD})
        assert r.status_code == 200, r.text
        assert r.json()["user"]["email"] == PATIENT_EMAIL
        assert "token" in r.json()

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": PATIENT_EMAIL, "password": "WrongPass123!"})
        assert r.status_code == 401

    def test_me_with_token(self):
        r = requests.get(f"{API}/auth/me",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        assert r.json()["email"] == PATIENT_EMAIL

    def test_me_missing_token(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token(self):
        r = requests.get(f"{API}/auth/me",
                         headers={"Authorization": "Bearer bogus.bogus.bogus"})
        assert r.status_code == 401


# ---------- WyshID ----------
class TestWyshID:
    def test_wyshid_me(self):
        r = requests.get(f"{API}/wyshid/me",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        b = r.json()
        assert b["wysh_id"] == state["patient_wysh"]
        assert b["email"] == PATIENT_EMAIL

    def test_lookup_as_doctor(self):
        r = requests.get(f"{API}/wyshid/{state['patient_wysh']}",
                         headers={"Authorization": f"Bearer {state['doctor_token']}"})
        assert r.status_code == 200
        assert r.json()["user"]["email"] == PATIENT_EMAIL

    def test_lookup_as_patient_forbidden(self):
        r = requests.get(f"{API}/wyshid/{state['patient_wysh']}",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 403


# ---------- Records ----------
class TestRecords:
    def test_create_record_as_patient(self):
        r = requests.post(f"{API}/records",
                          headers={"Authorization": f"Bearer {state['patient_token']}"},
                          json={"title": "BP reading", "record_type": "vitals",
                                "summary": "120/80", "data": {"systolic": 120, "diastolic": 80}})
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["patient_id"] == state["patient_id"]
        assert rec["record_id"].startswith("rec_")
        state["record_id"] = rec["record_id"]

    def test_list_records(self):
        r = requests.get(f"{API}/records",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        items = r.json()
        assert any(x["record_id"] == state["record_id"] for x in items)

    def test_timeline(self):
        r = requests.get(f"{API}/records/timeline",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        timeline = r.json()
        assert isinstance(timeline, list)
        # vitals event should appear
        assert any(e["id"] == state["record_id"] for e in timeline)


# ---------- Appointments ----------
class TestAppointments:
    def test_list_doctors(self):
        r = requests.get(f"{API}/appointments/doctors",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        docs = r.json()
        assert any(d["user_id"] == state["doctor_id"] for d in docs)
        for d in docs:
            assert "password_hash" not in d

    def test_book_appointment(self):
        r = requests.post(f"{API}/appointments",
                          headers={"Authorization": f"Bearer {state['patient_token']}"},
                          json={"doctor_id": state["doctor_id"],
                                "scheduled_at": "2026-02-01T10:00:00Z",
                                "mode": "telemedicine", "reason": "Checkup"})
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["status"] == "scheduled"
        state["apt_id"] = a["appointment_id"]

    def test_book_unknown_doctor_404(self):
        r = requests.post(f"{API}/appointments",
                          headers={"Authorization": f"Bearer {state['patient_token']}"},
                          json={"doctor_id": "usr_doesnotexist",
                                "scheduled_at": "2026-02-01T10:00:00Z"})
        assert r.status_code == 404

    def test_mine(self):
        r = requests.get(f"{API}/appointments/mine",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        appts = r.json()
        match = [a for a in appts if a["appointment_id"] == state["apt_id"]]
        assert match
        assert match[0]["doctor"]["user_id"] == state["doctor_id"]

    def test_cancel(self):
        r = requests.post(f"{API}/appointments/{state['apt_id']}/cancel",
                          headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        # verify status
        r2 = requests.get(f"{API}/appointments/mine",
                          headers={"Authorization": f"Bearer {state['patient_token']}"})
        a = next(x for x in r2.json() if x["appointment_id"] == state["apt_id"])
        assert a["status"] == "cancelled"


# ---------- OCR ----------
def _build_prescription_png() -> bytes:
    """Generate a real PNG with prescription-like text (not blank)."""
    img = Image.new("RGB", (900, 700), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        font_sm = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font
    lines = [
        ("Dr. R. Sharma, MD", font),
        ("WyshCare Medical Center", font_sm),
        ("Patient: John Doe   Age: 42   Date: 2026-01-12", font_sm),
        ("", font_sm),
        ("Rx", font),
        ("1. Amoxicillin 500 mg  - 1 cap TID x 7 days", font_sm),
        ("2. Paracetamol 650 mg  - 1 tab QID PRN fever", font_sm),
        ("3. Pantoprazole 40 mg  - 1 tab OD before breakfast", font_sm),
        ("", font_sm),
        ("Advice: plenty of fluids, rest, follow up in 1 week.", font_sm),
        ("Signature: Dr. R. Sharma", font_sm),
    ]
    y = 30
    for text, fnt in lines:
        d.text((40, y), text, fill=(0, 0, 0), font=fnt)
        y += 40
    # add a stamp/box so image isn't uniform variance
    d.rectangle((700, 560, 860, 660), outline=(0, 0, 0), width=3)
    d.text((720, 600), "STAMP", fill=(0, 0, 0), font=font_sm)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestOCR:
    def test_upload_prescription(self):
        png = _build_prescription_png()
        r = requests.post(
            f"{API}/ocr/prescriptions",
            headers={"Authorization": f"Bearer {state['patient_token']}"},
            files={"file": ("rx.png", png, "image/png")},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["prescription_id"].startswith("pres_")
        assert body["patient_id"] == state["patient_id"]
        assert body["status"] in ("extracted", "needs_review")
        assert "extracted" in body
        assert isinstance(body["extracted"].get("medications", []), list)
        state["pres_id"] = body["prescription_id"]

    def test_list_prescriptions(self):
        r = requests.get(f"{API}/ocr/prescriptions",
                         headers={"Authorization": f"Bearer {state['patient_token']}"})
        assert r.status_code == 200
        items = r.json()
        assert any(p["prescription_id"] == state["pres_id"] for p in items)

    def test_reject_bad_mime(self):
        r = requests.post(
            f"{API}/ocr/prescriptions",
            headers={"Authorization": f"Bearer {state['patient_token']}"},
            files={"file": ("rx.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400


# ---------- Admin ----------
class TestAdmin:
    def test_stats_admin(self):
        r = requests.get(f"{API}/admin/stats",
                         headers={"Authorization": f"Bearer {state['admin_token']}"})
        assert r.status_code == 200, r.text
        s = r.json()
        for k in ("users_total", "patients", "doctors", "wysh_ids_verified",
                  "prescriptions_ocr", "appointments_scheduled"):
            assert k in s

    def test_users_admin(self):
        r = requests.get(f"{API}/admin/users",
                         headers={"Authorization": f"Bearer {state['admin_token']}"})
        assert r.status_code == 200
        users = r.json()
        assert any(u["email"] == PATIENT_EMAIL for u in users)
        for u in users:
            assert "password_hash" not in u

    def test_audit_admin(self):
        r = requests.get(f"{API}/admin/audit?limit=200",
                         headers={"Authorization": f"Bearer {state['admin_token']}"})
        assert r.status_code == 200
        logs = r.json()
        actions = {l.get("action") for l in logs}
        # should include signup/login/record/ocr/appointment events
        for required in ("user.signup", "user.login", "record.create",
                         "ocr.prescription.extract", "appointment.book",
                         "appointment.cancel"):
            assert required in actions, f"missing audit action {required}; got {actions}"

    def test_admin_forbidden_for_patient(self):
        for path in ("/admin/stats", "/admin/users", "/admin/audit"):
            r = requests.get(f"{API}{path}",
                             headers={"Authorization": f"Bearer {state['patient_token']}"})
            assert r.status_code == 403, f"{path} returned {r.status_code}"
