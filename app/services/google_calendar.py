from __future__ import annotations

from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

from app.config import settings
from app.encryption import decrypt, encrypt

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange an authorization code for access_token + refresh_token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URI,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Use a refresh_token to obtain a new access_token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URI,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(
    conn: asyncpg.Connection,
    encrypted_access: str,
    encrypted_refresh: str,
    expires_at: datetime | None,
    slug: str,
) -> str:
    """Return a valid access token, refreshing if expired."""
    if expires_at and expires_at > datetime.now(timezone.utc):
        return decrypt(encrypted_access)

    refresh_token = decrypt(encrypted_refresh)
    token_data = await refresh_access_token(refresh_token)
    new_access = token_data["access_token"]
    new_expires = datetime.now(timezone.utc) + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )

    await conn.execute(
        "UPDATE calendar_connections "
        "SET google_access_token = $1, token_expires_at = $2 "
        "WHERE slug = $3",
        encrypt(new_access),
        new_expires,
        slug,
    )
    return new_access


async def get_free_busy(
    access_token: str, start_time: int, end_time: int, email: str
) -> list[dict]:
    """Fetch busy time blocks from Google Calendar FreeBusy API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CALENDAR_BASE}/freeBusy",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "timeMin": _epoch_to_rfc3339(start_time),
                "timeMax": _epoch_to_rfc3339(end_time),
                "items": [{"id": email}],
            },
        )
        resp.raise_for_status()
        data = resp.json()

    busy_slots: list[dict] = []
    for cal in data.get("calendars", {}).values():
        for block in cal.get("busy", []):
            busy_slots.append({
                "start_time": _rfc3339_to_epoch(block["start"]),
                "end_time": _rfc3339_to_epoch(block["end"]),
                "status": "busy",
            })
    return busy_slots


async def create_event(
    access_token: str,
    title: str,
    start_time: int,
    end_time: int,
    participant_email: str,
    participant_name: str,
    timezone: str = "UTC",
) -> dict:
    """Create a calendar event via Google Calendar Events API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_CALENDAR_BASE}/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"sendUpdates": "all"},
            json={
                "summary": title,
                "start": {"dateTime": _epoch_to_rfc3339(start_time), "timeZone": timezone},
                "end": {"dateTime": _epoch_to_rfc3339(end_time), "timeZone": timezone},
                "attendees": [
                    {"email": participant_email, "displayName": participant_name}
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()


def _epoch_to_rfc3339(epoch: int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _rfc3339_to_epoch(rfc: str) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(rfc).timestamp())
