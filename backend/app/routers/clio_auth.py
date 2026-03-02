"""Clio Manage OAuth 2.0 authentication endpoints.

Tokens are stored per-session in memory so multiple users can
each connect their own Clio account simultaneously.
Supports multiple Clio regions (US, CA, EU, AU).
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from loguru import logger

from app.config import settings
from app.services.token_store import (
    CLIO_REGIONS,
    get_session_id,
    get_tokens,
    set_tokens,
    clear_tokens,
)

router = APIRouter(prefix="/api/clio", tags=["clio-auth"])


def _resolve_base_url(region: str) -> str:
    """Map a region code to a Clio base URL."""
    base_url = CLIO_REGIONS.get(region.lower())
    if not base_url:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Clio region '{region}'. Valid: {', '.join(CLIO_REGIONS)}",
        )
    return base_url


@router.get("/auth")
async def clio_auth(
    request: Request,
    response: Response,
    region: str = "us",
):
    """Return the Clio OAuth authorization URL for the given region."""
    if not settings.clio_client_id:
        raise HTTPException(status_code=500, detail="CLIO_CLIENT_ID not configured")

    base_url = _resolve_base_url(region)

    # Store the chosen region in a short-lived cookie so the callback knows
    # which base URL to use for the token exchange.
    session_id = get_session_id(request, response)
    response.set_cookie(
        "clio_region", region.lower(), httponly=True, samesite="lax", max_age=600,
    )

    params = {
        "response_type": "code",
        "client_id": settings.clio_client_id,
        "redirect_uri": settings.clio_redirect_uri,
    }
    auth_url = f"{base_url}/oauth/authorize?{urlencode(params)}"
    logger.info(
        "Generated Clio auth URL for region={} (redirect_uri={})",
        region, settings.clio_redirect_uri,
    )
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

    # Recover the region from the cookie set in /auth
    region = request.cookies.get("clio_region", "us")
    base_url = CLIO_REGIONS.get(region, "https://app.clio.com")
    logger.info("OAuth callback for session {} (region={})", session_id[:8], region)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/oauth/token",
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
    set_tokens(session_id, body["access_token"], body["refresh_token"], base_url)

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
        "region": tokens.get("base_url", "") if tokens else None,
    }
