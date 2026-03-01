"""Clio Manage OAuth 2.0 authentication endpoints.

Handles the authorize redirect and token exchange callback.
Tokens are stored in-memory only — they do NOT persist to disk,
so each server restart starts disconnected.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from loguru import logger

from app.config import settings

router = APIRouter(prefix="/api/clio", tags=["clio-auth"])


@router.get("/auth")
async def clio_auth():
    """Return the Clio OAuth authorization URL for the frontend to redirect to."""
    if not settings.clio_client_id:
        raise HTTPException(status_code=500, detail="CLIO_CLIENT_ID not configured")

    params = {
        "response_type": "code",
        "client_id": settings.clio_client_id,
        "redirect_uri": settings.clio_redirect_uri,
    }
    auth_url = f"{settings.clio_base_url}/oauth/authorize?{urlencode(params)}"
    logger.info("Generated Clio auth URL (redirect_uri={})", settings.clio_redirect_uri)

    return {"auth_url": auth_url}


@router.get("/callback")
async def clio_callback(code: str | None = None, error: str | None = None):
    """Handle the OAuth callback: exchange authorization code for tokens."""
    if error:
        logger.error("Clio OAuth error: {}", error)
        raise HTTPException(status_code=400, detail=f"Clio OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    logger.info("Received Clio OAuth callback, exchanging code for tokens...")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.clio_base_url}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.clio_client_id,
                "client_secret": settings.clio_client_secret,
                "redirect_uri": settings.clio_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        detail = resp.text[:500]
        logger.error("Token exchange failed ({}): {}", resp.status_code, detail)
        raise HTTPException(
            status_code=502,
            detail=f"Token exchange failed ({resp.status_code}): {detail}",
        )

    body = resp.json()
    access_token = body["access_token"]
    refresh_token = body["refresh_token"]

    # Store in-memory ONLY — no disk persistence
    settings.clio_access_token = access_token
    settings.clio_refresh_token = refresh_token

    masked = access_token[:8] + "..." + access_token[-4:]
    logger.info("Clio OAuth complete. Access token: {}", masked)

    return RedirectResponse(url="/settings", status_code=302)


@router.post("/disconnect")
async def clio_disconnect():
    """Clear the current Clio connection (in-memory tokens)."""
    settings.clio_access_token = ""
    settings.clio_refresh_token = ""
    logger.info("Clio account disconnected")
    return {"status": "disconnected"}


@router.get("/status")
async def clio_status():
    """Check whether Clio tokens are configured."""
    has_token = bool(settings.clio_access_token)
    has_refresh = bool(settings.clio_refresh_token)

    return {
        "has_access_token": has_token,
        "has_refresh_token": has_refresh,
        "tokens_file_exists": False,
        "access_token_preview": (
            settings.clio_access_token[:8] + "..." + settings.clio_access_token[-4:]
            if has_token
            else None
        ),
    }
