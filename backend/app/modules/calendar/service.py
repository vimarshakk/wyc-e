from datetime import datetime


def build_meet_event(title: str, starts_at: datetime, duration_minutes: int = 30) -> dict:
    return {"summary": title, "start": starts_at.isoformat(), "duration_minutes": duration_minutes, "conference": "google_meet_pending"}
