"""MongoDB connection + collection accessors. Migration-aware schema layout."""
from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

_client = AsyncIOMotorClient(settings.MONGO_URL)
db = _client[settings.DB_NAME]

# Collections (named like future relational tables for clean migration)
users = db.wysh_users
sessions = db.wysh_sessions          # JWT/Google session refs (optional)
wysh_ids = db.wysh_identities        # WyshID identity records
records = db.wysh_health_records     # EMR records (prescriptions, labs, imaging)
prescriptions = db.wysh_prescriptions  # OCR-extracted structured prescriptions
appointments = db.wysh_appointments
audit_logs = db.wysh_audit_logs
files = db.wysh_files


async def ensure_indexes():
    await users.create_index("user_id", unique=True)
    await users.create_index("email", unique=True)
    await wysh_ids.create_index("user_id", unique=True)
    await wysh_ids.create_index("wysh_id", unique=True)
    await sessions.create_index("session_token", unique=True)
    await records.create_index([("patient_id", 1), ("created_at", -1)])
    await prescriptions.create_index([("patient_id", 1), ("created_at", -1)])
    await appointments.create_index([("patient_id", 1), ("scheduled_at", -1)])
    await appointments.create_index([("doctor_id", 1), ("scheduled_at", -1)])
    await audit_logs.create_index([("actor_id", 1), ("created_at", -1)])
    await files.create_index("file_id", unique=True)


def get_client():
    return _client
