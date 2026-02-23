from __future__ import annotations

import httpx

from app.config import settings

_BASE = settings.nylas_api_uri


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.nylas_api_key}",
        "Content-Type": "application/json",
    }


async def exchange_code_for_grant(code: str) -> dict:
    """Exchange an authorization code for a grant via Nylas token endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/v3/connect/token",
            headers={"Content-Type": "application/json"},
            json={
                "client_id": settings.nylas_client_id,
                "client_secret": settings.nylas_api_key,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.nylas_callback_uri,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_free_busy(
    grant_id: str, start_time: int, end_time: int, email: str
) -> list[dict]:
    """Fetch busy time blocks from Nylas Free/Busy API.

    Returns a list of time_slots dicts with 'start_time', 'end_time', 'status'.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/v3/grants/{grant_id}/calendars/free-busy",
            headers=_headers(),
            json={
                "start_time": start_time,
                "end_time": end_time,
                "emails": [email],
            },
        )
        resp.raise_for_status()
        data = resp.json()

    busy_slots: list[dict] = []
    for entry in data.get("data", []):
        for slot in entry.get("time_slots", []):
            if slot.get("status") == "busy":
                busy_slots.append(slot)
    return busy_slots


async def create_event(
    grant_id: str,
    title: str,
    start_time: int,
    end_time: int,
    participant_email: str,
    participant_name: str,
) -> dict:
    """Create a calendar event via Nylas Events API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_BASE}/v3/grants/{grant_id}/events",
            headers=_headers(),
            params={"calendar_id": "primary"},
            json={
                "title": title,
                "when": {
                    "start_time": start_time,
                    "end_time": end_time,
                },
                "participants": [
                    {"email": participant_email, "name": participant_name}
                ],
                "notify_participants": True,
            },
        )
        resp.raise_for_status()
        return resp.json()
