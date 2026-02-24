from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import get_pool
from app.encryption import encrypt
from app.services.google_calendar import exchange_code_for_tokens

router = APIRouter()

_GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_SCOPE = "https://www.googleapis.com/auth/calendar"


def _generate_slug() -> str:
    return secrets.token_urlsafe(6)[:8].lower()


@router.get("/auth/google")
async def auth_google():
    """Redirect the owner to Google OAuth consent screen."""
    owner_id = str(uuid.uuid4())
    params = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": owner_id,
    })
    return RedirectResponse(f"{_GOOGLE_AUTH_URI}?{params}")


@router.get("/auth/google/callback")
async def auth_google_callback(
    code: str = Query(...),
    state: str = Query(""),
):
    """Handle the OAuth callback from Google."""
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")

    owner_id = state
    try:
        token_data = await exchange_code_for_tokens(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google token exchange failed: {exc}")

    access_token: str = token_data.get("access_token", "")
    refresh_token: str = token_data.get("refresh_token", "")
    expires_in: int = token_data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        raise HTTPException(status_code=502, detail="Missing tokens in Google response")

    import httpx
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        # Fetch user email
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo", headers=headers,
        )
        email = resp.json().get("email", "") if resp.status_code == 200 else ""

        # Fetch calendar timezone
        resp = await client.get(
            "https://www.googleapis.com/calendar/v3/users/me/settings/timezone",
            headers=headers,
        )
        cal_tz = resp.json().get("value", "UTC") if resp.status_code == 200 else "UTC"

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    slug = _generate_slug()

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO calendar_connections
                (owner_id, slug, google_access_token, google_refresh_token,
                 token_expires_at, google_email, timezone)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (owner_id) DO UPDATE
               SET google_access_token  = EXCLUDED.google_access_token,
                   google_refresh_token  = EXCLUDED.google_refresh_token,
                   token_expires_at      = EXCLUDED.token_expires_at,
                   google_email          = EXCLUDED.google_email,
                   timezone              = EXCLUDED.timezone,
                   connected_at          = now(),
                   is_valid              = true
            """,
            owner_id,
            slug,
            encrypt(access_token),
            encrypt(refresh_token),
            expires_at,
            email,
            cal_tz,
        )
        row = await conn.fetchrow(
            "SELECT slug FROM calendar_connections WHERE owner_id = $1::uuid",
            owner_id,
        )

    final_slug = row["slug"] if row else slug
    return RedirectResponse(f"/setup.html?slug={final_slug}")
