"""WyshCare API entrypoint. Modular FastAPI monolith with DDD-ish boundaries."""
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import ensure_indexes
from app.modules.auth.router import router as auth_router
from app.modules.identity.router import router as identity_router
from app.modules.records.router import router as records_router
from app.modules.ocr.router import router as ocr_router
from app.modules.appointments.router import router as appointments_router
from app.modules.admin.router import router as admin_router
from app.modules.availability.router import router as availability_router
from app.modules.consultations.router import router as consultations_router
from app.modules.billing.router import router as billing_router
from app.modules.reminders.router import router as reminders_router
from app.modules.calendar.router import router as calendar_router
from app.modules.abdm.router import router as abdm_router
from app.modules.storage.service import init_storage

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("wyshcare")

app = FastAPI(title="WyshCare API", version="0.1.0")

api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"service": "wyshcare-api", "version": "0.1.0", "status": "ok"}


@api.get("/health")
async def health():
    return {"status": "healthy"}


api.include_router(auth_router)
api.include_router(identity_router)
api.include_router(records_router)
api.include_router(ocr_router)
api.include_router(appointments_router)
api.include_router(availability_router)
api.include_router(consultations_router)
api.include_router(billing_router)
api.include_router(reminders_router)
api.include_router(calendar_router)
api.include_router(abdm_router)
api.include_router(admin_router)

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_start():
    await ensure_indexes()
    init_storage()
    logger.info("WyshCare API ready")
