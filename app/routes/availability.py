from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.database import get_pool
from app.services.calendar import compute_available_slots
from app.services.google_calendar import get_free_busy, get_valid_access_token

router = APIRouter()


@router.get("/api/availability")
async def availability(
    slug: str = Query(...),
    date_str: str = Query(..., alias="date"),
):
    if not slug:
        raise HTTPException(status_code=400, detail="slug is required")

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT google_access_token, google_refresh_token, token_expires_at, "
            "google_email, timezone, "
            "business_hours_start, business_hours_end, slot_duration_minutes "
            "FROM calendar_connections WHERE slug = $1 AND is_valid = true",
            slug,
        )
        if not row:
            raise HTTPException(status_code=404, detail="No calendar connected for this owner")

        try:
            access_token = await get_valid_access_token(
                conn,
                row["google_access_token"],
                row["google_refresh_token"],
                row["token_expires_at"],
                slug,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Token refresh failed: {exc}")

    email = row["google_email"] or ""
    tz = row["timezone"] or "UTC"
    slot_duration = row["slot_duration_minutes"] or settings.slot_duration_minutes

    bh_start = time.fromisoformat(row["business_hours_start"] or settings.business_hours_start)
    bh_end = time.fromisoformat(row["business_hours_end"] or settings.business_hours_end)

    day_start_dt = datetime.combine(target_date, bh_start, tzinfo=timezone.utc)
    day_end_dt = datetime.combine(target_date, bh_end, tzinfo=timezone.utc)

    try:
        busy_blocks = await get_free_busy(
            access_token,
            int(day_start_dt.timestamp()),
            int(day_end_dt.timestamp()),
            email,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google free/busy call failed: {exc}")

    slots = compute_available_slots(
        busy_blocks, target_date, bh_start, bh_end, slot_duration,
    )

    return {
        "date": date_str,
        "timezone": tz,
        "slot_duration_minutes": slot_duration,
        "slots": slots,
        "owner_email": email,
    }
