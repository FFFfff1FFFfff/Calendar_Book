from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_pool

router = APIRouter()


class OwnerSettings(BaseModel):
    timezone: str = "UTC"
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    slot_duration_minutes: int = 30


@router.get("/api/owner/{slug}")
async def get_owner(slug: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT slug, google_email, timezone, business_hours_start, "
            "business_hours_end, slot_duration_minutes "
            "FROM calendar_connections WHERE slug = $1 AND is_valid = true",
            slug,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Owner not found")

    return {
        "slug": row["slug"],
        "email": row["google_email"],
        "timezone": row["timezone"],
        "business_hours_start": row["business_hours_start"],
        "business_hours_end": row["business_hours_end"],
        "slot_duration_minutes": row["slot_duration_minutes"],
    }


@router.post("/api/owner/{slug}/settings")
async def update_settings(slug: str, body: OwnerSettings):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE calendar_connections
            SET timezone = $1,
                business_hours_start = $2,
                business_hours_end = $3,
                slot_duration_minutes = $4
            WHERE slug = $5 AND is_valid = true
            """,
            body.timezone,
            body.business_hours_start,
            body.business_hours_end,
            body.slot_duration_minutes,
            slug,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Owner not found")

    return {"status": "saved"}
