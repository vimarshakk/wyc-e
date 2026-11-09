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
lab_reports = db.wysh_lab_reports
appointments = db.wysh_appointments
consultations = db.wysh_consultations
consultation_notes = db.wysh_consultation_notes
invoices = db.wysh_invoices
invoice_lines = db.wysh_invoice_lines
reminders = db.wysh_care_reminders
reminder_preferences = db.wysh_reminder_preferences
reminder_deliveries = db.wysh_reminder_deliveries
calendar_connections = db.wysh_calendar_connections
calendar_oauth_states = db.wysh_calendar_oauth_states
abdm_transactions = db.wysh_abdm_transactions
abdm_callback_events = db.wysh_abdm_callback_events
abdm_patient_links = db.wysh_abdm_patient_links
abdm_consents = db.wysh_abdm_consents
uhi_transactions = db.wysh_uhi_transactions
nhcx_episodes = db.wysh_nhcx_episodes
nhcx_events = db.wysh_nhcx_events
partner_tasks = db.wysh_partner_tasks
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
    await lab_reports.create_index([("patient_id", 1), ("created_at", -1)])
    await appointments.create_index([("patient_id", 1), ("scheduled_at", -1)])
    await appointments.create_index([("doctor_id", 1), ("scheduled_at", -1)])
    await appointments.create_index(
        [("doctor_id", 1), ("scheduled_at", 1)],
        unique=True,
        partialFilterExpression={"status": "scheduled"},
    )
    await audit_logs.create_index([("actor_id", 1), ("created_at", -1)])
    await files.create_index("file_id", unique=True)
    await consultations.create_index("consultation_id", unique=True)
    await consultations.create_index("appointment_id", unique=True)
    await consultations.create_index([("patient_id", 1), ("scheduled_at", -1)])
    await consultations.create_index([("doctor_id", 1), ("scheduled_at", -1)])
    await consultation_notes.create_index([("consultation_id", 1), ("created_at", -1)])
    await invoices.create_index("invoice_id", unique=True)
    await invoices.create_index([("patient_id", 1), ("created_at", -1)])
    await invoice_lines.create_index([("invoice_id", 1), ("line_number", 1)])
    await reminders.create_index("reminder_id", unique=True)
    await reminders.create_index([("patient_id", 1), ("due_at", 1)])
    await reminder_preferences.create_index("patient_id", unique=True)
    await calendar_connections.create_index("connection_id", unique=True)
    await calendar_oauth_states.create_index("state", unique=True)
    await abdm_transactions.create_index("request_id", unique=True, sparse=True)
    await abdm_transactions.create_index([("patient_id", 1), ("created_at", -1)])
    await abdm_callback_events.create_index([("event_type", 1), ("correlation_id", 1)], unique=True, sparse=True)
    await abdm_patient_links.create_index("patient_id", unique=True)
    await abdm_consents.create_index("consent_id", unique=True, sparse=True)
    await uhi_transactions.create_index("transaction_id", unique=True)
    await uhi_transactions.create_index([("patient_id", 1), ("created_at", -1)])
    await nhcx_episodes.create_index("episode_id", unique=True)
    await nhcx_episodes.create_index([("patient_id", 1), ("created_at", -1)])
    await nhcx_events.create_index([("correlation_id", 1), ("api_call_id", 1)], unique=True)
    await partner_tasks.create_index([("partner_id", 1), ("status", 1)])


def get_client():
    return _client
