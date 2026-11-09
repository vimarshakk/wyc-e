from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import settings

client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


def get_database() -> AsyncIOMotorDatabase | None:
    global client, database
    if database is None:
        try:
            client = AsyncIOMotorClient(settings.mongo_url, serverSelectionTimeoutMS=500)
            database = client[settings.mongo_db]
        except Exception:
            database = None
    return database


async def ping_db() -> str:
    db = get_database()
    if db is None:
        return "unavailable"
    try:
        await db.command("ping")
        return "connected"
    except Exception:
        return "unavailable"


async def ensure_indexes() -> None:
    db = get_database()
    if db is None:
        return
    try:
        await db.users.create_index("email", unique=True, sparse=True)
        await db.users.create_index("phone", unique=True, sparse=True)
        await db.appointments.create_index([("provider_id", 1), ("starts_at", 1)])
        await db.records.create_index([("patient_id", 1), ("created_at", -1)])
        await db.audit_events.create_index([("actor_id", 1), ("created_at", -1)])
    except Exception:
        return


async def close_db() -> None:
    global client, database
    if client:
        client.close()
    client = None
    database = None


def collection(name: str) -> Any:
    db = get_database()
    return db[name] if db is not None else None
