"""Clio Manage OAuth 2.0 authentication endpoints.

Tokens are stored per-session in memory so multiple users can
each connect their own Clio account simultaneously.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from loguru import logger

from app.config import settings
from app.services.token_store import (
    get_session_id,
    get_tokens,
    set_tokens,
    clear_tokens,
)

router = APIRouter(prefix="/api/clio", tags=["clio-auth"])


@router.get("/auth")
async def clio_auth(request: Request, response: Response):
    """Return the Clio OAuth authorization URL."""
    if not settings.clio_client_id:
        raise HTTPException(status_code=500, detail="CLIO_CLIENT_ID not configured")

    # Ensure session cookie exists before redirect
    get_session_id(request, response)

    params = {
        "response_type": "code",
        "client_id": settings.clio_client_id,
        "redirect_uri": settings.clio_redirect_uri,
    }
    auth_url = f"{settings.clio_base_url}/oauth/authorize?{urlencode(params)}"
    logger.info("Generated Clio auth URL (redirect_uri={})", settings.clio_redirect_uri)
    return {"auth_url": auth_url}


@router.get("/callback")
async def clio_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    error: str | None = None,
):
    """Handle the OAuth callback: exchange code for tokens, store per-session."""
    if error:
        logger.error("Clio OAuth error: {}", error)
        raise HTTPException(status_code=400, detail=f"Clio OAuth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    session_id = get_session_id(request, response)
    logger.info("OAuth callback for session {}", session_id[:8])

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
    set_tokens(session_id, body["access_token"], body["refresh_token"])

    masked = body["access_token"][:8] + "..." + body["access_token"][-4:]
    logger.info("Clio OAuth complete for session {}. Token: {}", session_id[:8], masked)

    redirect = RedirectResponse(url="/settings", status_code=302)
    # Ensure the session cookie is on the redirect response too
    redirect.set_cookie("sid", session_id, httponly=True, samesite="lax", max_age=86400)
    return redirect


@router.post("/disconnect")
async def clio_disconnect(request: Request, response: Response):
    """Clear the Clio connection for this session."""
    session_id = get_session_id(request, response)
    clear_tokens(session_id)
    return {"status": "disconnected"}


@router.get("/status")
async def clio_status(request: Request, response: Response):
    """Check whether this session has Clio tokens."""
    session_id = get_session_id(request, response)
    tokens = get_tokens(session_id)

    has_token = bool(tokens and tokens.get("access_token"))

    return {
        "has_access_token": has_token,
        "has_refresh_token": bool(tokens and tokens.get("refresh_token")),
        "tokens_file_exists": False,
        "access_token_preview": (
            tokens["access_token"][:8] + "..." + tokens["access_token"][-4:]
            if has_token
            else None
        ),
    }
