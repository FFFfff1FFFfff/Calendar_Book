from __future__ import annotations

import secrets
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.config import settings
from app.database import get_pool
from app.encryption import encrypt
from app.services.nylas_client import exchange_code_for_grant

router = APIRouter()


def _generate_slug() -> str:
    return secrets.token_urlsafe(6)[:8].lower()


@router.get("/auth/google")
async def auth_google():
    """Redirect the owner to Nylas Hosted Auth."""
    owner_id = str(uuid.uuid4())
    params = urlencode({
        "client_id": settings.nylas_client_id,
        "redirect_uri": settings.nylas_callback_uri,
        "response_type": "code",
        "provider": "google",
        "state": owner_id,
    })
    return RedirectResponse(f"{settings.nylas_api_uri}/v3/connect/auth?{params}")


@router.get("/auth/google/callback")
async def auth_google_callback(
    code: str = Query(...),
    state: str = Query(""),
):
    """Handle the OAuth callback from Nylas."""
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")

    owner_id = state
    try:
        token_data = await exchange_code_for_grant(code)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nylas token exchange failed: {exc}")

    grant_id: str = token_data.get("grant_id", "")
    email: str = token_data.get("email", "")
    if not grant_id:
        raise HTTPException(status_code=502, detail="No grant_id in Nylas response")

    encrypted_grant_id = encrypt(grant_id)
    slug = _generate_slug()

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO calendar_connections (owner_id, slug, nylas_grant_id, google_email)
            VALUES ($1::uuid, $2, $3, $4)
            ON CONFLICT (owner_id) DO UPDATE
               SET nylas_grant_id = EXCLUDED.nylas_grant_id,
                   google_email   = EXCLUDED.google_email,
                   connected_at   = now(),
                   is_valid       = true
            """,
            owner_id,
            slug,
            encrypted_grant_id,
            email,
        )
        row = await conn.fetchrow(
            "SELECT slug FROM calendar_connections WHERE owner_id = $1::uuid",
            owner_id,
        )

    final_slug = row["slug"] if row else slug
    return RedirectResponse(f"/setup.html?slug={final_slug}")
