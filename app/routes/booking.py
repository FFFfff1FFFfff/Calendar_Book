from __future__ import annotations

import time as _time
import uuid as _uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.database import get_pool
from app.encryption import decrypt
from app.services.nylas_client import create_event, get_free_busy

router = APIRouter()

# ---------------------------------------------------------------------------
# Simple in-memory sliding-window rate limiter (per IP, 10 req / 60s)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class BookingRequest(BaseModel):
    owner_id: str
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


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post("/api/book", response_model=BookingResponse)
async def book(body: BookingRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    if not body.owner_id:
        raise HTTPException(status_code=400, detail="owner_id is required")
    try:
        _uuid.UUID(body.owner_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="owner_id must be a valid UUID")

    if body.end_time <= body.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT nylas_grant_id, google_email FROM calendar_connections "
            "WHERE owner_id = $1::uuid AND is_valid = true",
            body.owner_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="No calendar connected for this owner")

    grant_id = decrypt(row["nylas_grant_id"])
    email = row["google_email"] or ""

    # Re-check free/busy to prevent double booking
    try:
        busy = await get_free_busy(grant_id, body.start_time, body.end_time, email)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nylas free/busy check failed: {exc}")

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
            grant_id=grant_id,
            title=title,
            start_time=body.start_time,
            end_time=body.end_time,
            participant_email=body.customer_email,
            participant_name=body.customer_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to create event: {exc}")

    event = event_data.get("data", event_data)

    return BookingResponse(
        status="confirmed",
        event_id=event.get("id", ""),
        title=title,
        start_time=body.start_time,
        end_time=body.end_time,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
    )
