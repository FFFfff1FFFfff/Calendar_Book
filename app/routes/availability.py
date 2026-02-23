from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.database import get_pool
from app.encryption import decrypt
from app.services.calendar import compute_available_slots
from app.services.nylas_client import get_free_busy

router = APIRouter()


@router.get("/api/availability")
async def availability(
    owner_id: str = Query(...),
    date_str: str = Query(..., alias="date"),
):
    if not owner_id:
        raise HTTPException(status_code=400, detail="owner_id is required")
    try:
        _uuid.UUID(owner_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="owner_id must be a valid UUID")

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT nylas_grant_id, google_email FROM calendar_connections "
            "WHERE owner_id = $1::uuid AND is_valid = true",
            owner_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="No calendar connected for this owner")

    grant_id = decrypt(row["nylas_grant_id"])
    email = row["google_email"] or ""

    bh_start = time.fromisoformat(settings.business_hours_start)
    bh_end = time.fromisoformat(settings.business_hours_end)

    day_start_dt = datetime.combine(target_date, bh_start, tzinfo=timezone.utc)
    day_end_dt = datetime.combine(target_date, bh_end, tzinfo=timezone.utc)

    try:
        busy_blocks = await get_free_busy(
            grant_id,
            int(day_start_dt.timestamp()),
            int(day_end_dt.timestamp()),
            email,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nylas free/busy call failed: {exc}")

    slots = compute_available_slots(
        busy_blocks,
        target_date,
        bh_start,
        bh_end,
        settings.slot_duration_minutes,
    )

    return {
        "date": date_str,
        "timezone": "UTC",
        "slot_duration_minutes": settings.slot_duration_minutes,
        "slots": slots,
        "owner_email": email,
    }
