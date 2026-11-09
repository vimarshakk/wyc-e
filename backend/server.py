from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import close_db, ensure_indexes, ping_db
from app.modules.abdm.router import router as abdm_router
from app.modules.admin.router import router as admin_router
from app.modules.appointments.router import router as appointments_router
from app.modules.auth.router import router as auth_router
from app.modules.availability.router import router as availability_router
from app.modules.billing.router import router as billing_router
from app.modules.calendar.router import router as calendar_router
from app.modules.consultations.router import router as consultations_router
from app.modules.identity.router import router as identity_router
from app.modules.nhcx.router import router as nhcx_router
from app.modules.ocr.router import router as ocr_router
from app.modules.records.router import router as records_router
from app.modules.reminders.router import router as reminders_router
from app.modules.uhi.router import router as uhi_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    yield
    await close_db()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name, "database": await ping_db()}


prefix = settings.api_prefix
for module_router in (
    auth_router, admin_router, appointments_router, availability_router,
    billing_router, calendar_router, consultations_router, identity_router,
    nhcx_router, ocr_router, records_router, reminders_router, abdm_router,
    uhi_router,
):
    app.include_router(module_router, prefix=prefix)
