"""Doctor availability + slot generation engine.

Data model (Mongo collections, migration-friendly):
  wysh_availability: weekly recurring schedule
    { doctor_id, day_of_week (0=Mon..6=Sun), start_time "HH:MM", end_time "HH:MM",
      slot_minutes (int), updated_at }
  wysh_time_off: specific blocked windows
    { time_off_id, doctor_id, start_at ISO, end_at ISO, reason }
"""
import uuid
from datetime import datetime, timezone, timedelta, time as dtime, date as ddate
from typing import List, Optional, Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, conint
from ...core.db import db, appointments, users
from ...core.deps import get_current_user, require_role
from ...core.audit import write_audit

router = APIRouter(prefix="/availability", tags=["availability"])

availability_col = db.wysh_availability
time_off_col = db.wysh_time_off
CLINIC_TIMEZONE = ZoneInfo("Asia/Kolkata")


class WeeklyBlock(BaseModel):
    day_of_week: conint(ge=0, le=6)
    start_time: str  # "HH:MM"
    end_time: str
    slot_minutes: conint(ge=5, le=240) = 30


class WeeklyScheduleBody(BaseModel):
    blocks: List[WeeklyBlock]


class TimeOffCreate(BaseModel):
    start_at: str  # ISO
    end_at: str
    reason: Optional[str] = None


def _parse_hm(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def _parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CLINIC_TIMEZONE)
    return dt


@router.get("/me")
async def my_schedule(user: dict = Depends(require_role("doctor"))):
    blocks = await availability_col.find({"doctor_id": user["user_id"]}, {"_id": 0}).to_list(50)
    return {"doctor_id": user["user_id"], "blocks": blocks}


@router.put("/me")
async def set_my_schedule(body: WeeklyScheduleBody, user: dict = Depends(require_role("doctor"))):
    daily_blocks = {}
    for b in body.blocks:
        try:
            s, e = _parse_hm(b.start_time), _parse_hm(b.end_time)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid time format in block dow={b.day_of_week}")
        if e <= s:
            raise HTTPException(status_code=400, detail=f"end_time must be after start_time (dow={b.day_of_week})")
        daily_blocks.setdefault(b.day_of_week, []).append((s, e))

    for day, windows in daily_blocks.items():
        windows.sort()
        for (_, previous_end), (start, _) in zip(windows, windows[1:]):
            if start < previous_end:
                raise HTTPException(status_code=400, detail=f"Weekly blocks must not overlap (dow={day})")

    await availability_col.delete_many({"doctor_id": user["user_id"]})
    now = datetime.now(timezone.utc).isoformat()
    if body.blocks:
        await availability_col.insert_many([
            {**b.model_dump(), "doctor_id": user["user_id"], "updated_at": now}
            for b in body.blocks
        ])
    await write_audit(user["user_id"], "availability.set", "availability", user["user_id"],
                      {"block_count": len(body.blocks)})
    return {"ok": True, "blocks": len(body.blocks)}


@router.get("/time-off/me")
async def my_time_off(user: dict = Depends(require_role("doctor"))):
    cur = time_off_col.find({"doctor_id": user["user_id"]}, {"_id": 0}).sort("start_at", 1)
    return await cur.to_list(200)


@router.post("/time-off")
async def add_time_off(body: TimeOffCreate, user: dict = Depends(require_role("doctor"))):
    try:
        s = _parse_iso(body.start_at)
        e = _parse_iso(body.end_at)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid datetime (ISO required)")
    if e <= s:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")
    doc = {
        "time_off_id": f"toff_{uuid.uuid4().hex[:14]}",
        "doctor_id": user["user_id"],
        "start_at": s.isoformat(),
        "end_at": e.isoformat(),
        "reason": body.reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await time_off_col.insert_one(doc)
    doc.pop("_id", None)
    await write_audit(user["user_id"], "availability.time_off.add", "time_off", doc["time_off_id"])
    return doc


@router.delete("/time-off/{toff_id}")
async def delete_time_off(toff_id: str, user: dict = Depends(require_role("doctor"))):
    res = await time_off_col.delete_one({"time_off_id": toff_id, "doctor_id": user["user_id"]})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Not found")
    await write_audit(user["user_id"], "availability.time_off.delete", "time_off", toff_id)
    return {"ok": True}


@router.get("/{doctor_id}/slots")
async def slots(
    doctor_id: str,
    date: str = Query(..., description="YYYY-MM-DD"),
    user: dict = Depends(get_current_user),
):
    """Return list of available slot start times (ISO) for the given doctor and date."""
    doc = await users.find_one({"user_id": doctor_id, "role": "doctor"}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    try:
        y, m, d = [int(x) for x in date.split("-")]
        target = ddate(y, m, d)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date (use YYYY-MM-DD)")

    now = datetime.now(CLINIC_TIMEZONE)
    if target < now.date():
        return {"doctor_id": doctor_id, "date": date, "slots": []}

    dow = target.weekday()  # 0=Mon
    blocks = await availability_col.find(
        {"doctor_id": doctor_id, "day_of_week": dow}, {"_id": 0}
    ).to_list(20)
    if not blocks:
        return {"doctor_id": doctor_id, "date": date, "slots": []}

    # Generate slot grid
    candidates: List[tuple[datetime, datetime]] = []
    for b in blocks:
        try:
            s = _parse_hm(b["start_time"]); e = _parse_hm(b["end_time"])
        except Exception:
            continue
        step = timedelta(minutes=int(b.get("slot_minutes", 30)))
        cur_dt = datetime.combine(target, s, tzinfo=CLINIC_TIMEZONE)
        end_dt = datetime.combine(target, e, tzinfo=CLINIC_TIMEZONE)
        while cur_dt + step <= end_dt:
            candidates.append((cur_dt, cur_dt + step))
            cur_dt += step

    # Stored appointment timestamps may retain historical UTC or current clinic offsets.
    # Normalize them before comparing instants with locally-defined weekly hours.
    booked_cur = appointments.find({
        "doctor_id": doctor_id,
        "status": {"$ne": "cancelled"},
    }, {"_id": 0, "scheduled_at": 1})
    booked = set()
    for booked_appointment in await booked_cur.to_list(500):
        try:
            booked.add(_parse_iso(booked_appointment["scheduled_at"]).astimezone(CLINIC_TIMEZONE))
        except (KeyError, TypeError, ValueError):
            continue

    # Exclude time-off windows
    toffs = await time_off_col.find({"doctor_id": doctor_id}, {"_id": 0}).to_list(200)
    toff_parsed = []
    for time_off in toffs:
        try:
            toff_parsed.append((_parse_iso(time_off["start_at"]), _parse_iso(time_off["end_at"])))
        except (KeyError, TypeError, ValueError):
            continue

    available = []
    for slot_start, slot_end in sorted(set(candidates), key=lambda slot: slot[0]):
        if slot_start <= now or slot_start in booked:
            continue
        if any(slot_start < time_off_end and slot_end > time_off_start for time_off_start, time_off_end in toff_parsed):
            continue
        available.append(slot_start.isoformat())

    return {
        "doctor_id": doctor_id,
        "date": date,
        "doctor": {"name": doc["name"], "specialty": doc.get("specialty"), "wysh_id": doc.get("wysh_id")},
        "slots": available,
    }
