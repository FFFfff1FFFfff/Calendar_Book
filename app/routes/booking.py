from __future__ import annotations

import time as _time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.database import get_pool
from app.services.google_calendar import (
    create_event,
    get_free_busy,
    get_valid_access_token,
)

router = APIRouter()

_RATE_WINDOW = 60
_RATE_LIMIT = 10
_request_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    now = _time.time()
    window_start = now - _RATE_WINDOW
    log = _request_log[ip]
    _request_log[ip] = [t for t in log if t > window_start]
    if len(_request_log[ip]) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests – try again later")
    _request_log[ip].append(now)


class BookingRequest(BaseModel):
    slug: str
    start_time: int
    end_time: int
    customer_name: str
    customer_email: EmailStr


class BookingResponse(BaseModel):
    status: str
    event_id: str
    title: str
    start_time: int
    end_time: int
    customer_name: str
    customer_email: str


@router.post("/api/book", response_model=BookingResponse)
async def book(body: BookingRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    if not body.slug:
        raise HTTPException(status_code=400, detail="slug is required")
    if body.end_time <= body.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT google_access_token, google_refresh_token, token_expires_at, "
            "google_email, timezone FROM calendar_connections "
            "WHERE slug = $1 AND is_valid = true",
            body.slug,
        )
        if not row:
            raise HTTPException(status_code=404, detail="No calendar connected for this owner")

        try:
            access_token = await get_valid_access_token(
                conn,
                row["google_access_token"],
                row["google_refresh_token"],
                row["token_expires_at"],
                body.slug,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Token refresh failed: {exc}")

    email = row["google_email"] or ""
    owner_tz = row["timezone"] or "UTC"

    # Check local bookings first (authoritative, no propagation delay)
    async with pool.acquire() as conn:
        conflict = await conn.fetchval(
            "SELECT 1 FROM bookings "
            "WHERE slug = $1 AND start_time < $2 AND end_time > $3 LIMIT 1",
            body.slug, body.end_time, body.start_time,
        )
    if conflict:
        raise HTTPException(status_code=409, detail="Time slot is no longer available")

    try:
        busy = await get_free_busy(access_token, body.start_time, body.end_time, email)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google free/busy check failed: {exc}")

    slot_start = datetime.fromtimestamp(body.start_time, tz=timezone.utc)
    slot_end = datetime.fromtimestamp(body.end_time, tz=timezone.utc)

    for block in busy:
        b_start = datetime.fromtimestamp(block["start_time"], tz=timezone.utc)
        b_end = datetime.fromtimestamp(block["end_time"], tz=timezone.utc)
        if b_start < slot_end and b_end > slot_start:
            raise HTTPException(status_code=409, detail="Time slot is no longer available")

    title = f"Booking: {body.customer_name}"

    try:
        event_data = await create_event(
            access_token=access_token,
            title=title,
            start_time=body.start_time,
            end_time=body.end_time,
            participant_email=body.customer_email,
            participant_name=body.customer_name,
            timezone=owner_tz,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to create event: {exc}")

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bookings (slug, start_time, end_time) VALUES ($1, $2, $3)",
            body.slug, body.start_time, body.end_time,
        )

    return BookingResponse(
        status="confirmed",
        event_id=event_data.get("id", ""),
        title=title,
        start_time=body.start_time,
        end_time=body.end_time,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
    )
